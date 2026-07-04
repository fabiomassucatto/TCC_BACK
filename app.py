import qrcode
import io
import secrets
import sqlite3
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timedelta
from flask import (Flask, render_template, request,
                   redirect, session, send_file, jsonify)

app = Flask(__name__)
app.secret_key = "tcc_gestao_transporte_2026"

# ─────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────
QR_VALIDADE_SEGUNDOS = 20      # QR expira em 20 segundos
LIMITE_DISTANCIA_METROS = 100  # raio máximo permitido (ajuste após testes de campo)

# ─────────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row   # permite acessar colunas por nome
    return conn

def criar_tabelas():
    conn = get_db()

    # Tabela de usuários (já existia — sem alterar colunas existentes)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nome    VARCHAR(100) NOT NULL,
            email   VARCHAR(100) UNIQUE,
            senha   VARCHAR(100) NOT NULL,
            ponto   VARCHAR(100) NOT NULL,
            tipo    VARCHAR(20)  NOT NULL,
            lat_residencia  REAL,
            lng_residencia  REAL
        )
    """)
        

    # Adiciona colunas de GPS à tabela existente (ignora erro se já existirem)
    for col, tipo in [("lat_residencia", "REAL"), ("lng_residencia", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
        except Exception:
            pass

    # Presenças (já existia — sem alterar colunas existentes)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS presencas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id      INTEGER,
            motorista_id    INTEGER,
            data_hora       DATETIME,
            lat_aluno       REAL,
            lng_aluno       REAL,
            lat_motorista   REAL,
            lng_motorista   REAL,
            distancia_m     REAL,
            FOREIGN KEY (usuario_id)   REFERENCES usuarios(id),
            FOREIGN KEY (motorista_id) REFERENCES usuarios(id)
        )
    """)

    # Adiciona colunas de GPS à presencas se não existirem
    for col, tipo in [("lat_aluno","REAL"),("lng_aluno","REAL"),
                      ("lat_motorista","REAL"),("lng_motorista","REAL"),
                      ("distancia_m","REAL")]:
        try:
            conn.execute(f"ALTER TABLE presencas ADD COLUMN {col} {tipo}")
        except Exception:
            pass

    # Tokens de QR Code dinâmico
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qr_tokens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            motorista_id INTEGER,
            token       TEXT UNIQUE,
            criado_em   DATETIME,
            expira_em   DATETIME,
            usado       INTEGER DEFAULT 0,
            FOREIGN KEY (motorista_id) REFERENCES usuarios(id)
        )
    """)

    # Localização atual do motorista (1 linha por motorista, upsert)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS motorista_localizacao (
            motorista_id INTEGER PRIMARY KEY,
            latitude     REAL,
            longitude    REAL,
            atualizado_em DATETIME,
            FOREIGN KEY (motorista_id) REFERENCES usuarios(id)
        )
    """)

    conn.commit()
    conn.close()

criar_tabelas()

# ─────────────────────────────────────────────
# UTILITÁRIO: Haversine
# ─────────────────────────────────────────────
def calcular_distancia_metros(lat1, lng1, lat2, lng2):
    R = 6_371_000
    f1, f2 = radians(lat1), radians(lat2)
    df = radians(lat2 - lat1)
    dl = radians(lng2 - lng1)
    a = sin(df/2)**2 + cos(f1) * cos(f2) * sin(dl/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

# ─────────────────────────────────────────────
# ROTAS GERAIS
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return redirect("/login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        tipo_form = request.form.get("tipo", "usuario")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE email=? AND senha=?",
            (email, senha)
        ).fetchone()
        conn.close()

        if user:
            # Verifica se o tipo bate com o selecionado na tela
            if user["tipo"] != tipo_form:
                erro = "Perfil incorreto para este usuário."
            else:
                session["user"]      = user["nome"]
                session["user_id"]   = user["id"]
                session["user_tipo"] = user["tipo"]

                if user["tipo"] == "motorista":
                    return redirect("/dashboard")
                else:
                    return redirect("/scanner")
        else:
            erro = "E-mail ou senha incorretos."

    return render_template("login.html", erro=erro)

# ─────────────────────────────────────────────
# CADASTRO
# ─────────────────────────────────────────────
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    erro = None
    if request.method == "POST":
        nome  = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]
        ponto = request.form["ponto"]

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO usuarios (nome, email, senha, ponto, tipo) VALUES (?,?,?,?,?)",
                (nome, email, senha, ponto, "usuario")
            )
            conn.commit()
            conn.close()
            return redirect("/login")
        except sqlite3.IntegrityError:
            erro = "E-mail já cadastrado."

    return render_template("cadastro.html", erro=erro)

# ─────────────────────────────────────────────
# DASHBOARD DO MOTORISTA
# ─────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    if session.get("user_tipo") != "motorista":
        return redirect("/login")

    motorista_id = session["user_id"]
    conn = get_db()

    # Presenças de hoje deste motorista
    hoje = datetime.now().strftime("%Y-%m-%d")
    presencas = conn.execute("""
        SELECT u.nome,
               strftime('%H:%M', p.data_hora) AS hora,
               p.distancia_m,
               p.lat_aluno,
               p.lng_aluno
        FROM presencas p
        JOIN usuarios u ON u.id = p.usuario_id
        WHERE p.motorista_id = ?
          AND date(p.data_hora) = ?
        ORDER BY p.data_hora DESC
    """, (motorista_id, hoje)).fetchall()

    # Pontos residenciais cadastrados pelos passageiros para o mapa
    pontos_mapa = conn.execute("""
        SELECT u.nome, u.ponto, u.lat_residencia AS lat, u.lng_residencia AS lng
        FROM usuarios u
        WHERE u.tipo = 'usuario'
          AND u.lat_residencia IS NOT NULL
    """).fetchall()

    conn.close()

    pontos_unicos = len(set(p["ponto"] for p in presencas))

    return render_template(
        "dashboard.html",
        presencas=[dict(p) for p in presencas],
        pontos_mapa=[dict(p) for p in pontos_mapa],
        pontos_unicos=pontos_unicos,
    )

# ─────────────────────────────────────────────
# QR CODE DINÂMICO (gerado a cada chamada)
# ─────────────────────────────────────────────
@app.route("/motorista/qr_atual")
def qr_atual():
    if session.get("user_tipo") != "motorista":
        return jsonify({"erro": "Acesso negado"}), 403

    motorista_id = session["user_id"]
    token    = secrets.token_urlsafe(16)
    agora    = datetime.now()
    expira   = agora + timedelta(seconds=QR_VALIDADE_SEGUNDOS)

    conn = get_db()
    conn.execute("""
        INSERT INTO qr_tokens (motorista_id, token, criado_em, expira_em)
        VALUES (?, ?, ?, ?)
    """, (motorista_id, token, agora, expira))
    conn.commit()
    conn.close()

    # Gera imagem PNG do QR
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# Rota legada — mantida para compatibilidade com motorista_login.html antigo
@app.route("/gerar_qr/<int:motorista_id>")
def gerar_qr(motorista_id):
    return redirect("/motorista/qr_atual")

# ─────────────────────────────────────────────
# LOCALIZAÇÃO DO MOTORISTA (enviada pelo front)
# ─────────────────────────────────────────────
@app.route("/motorista/atualizar_localizacao", methods=["POST"])
def atualizar_localizacao():
    if session.get("user_tipo") != "motorista":
        return jsonify({"erro": "Acesso negado"}), 403

    dados = request.get_json()
    lat = dados.get("lat")
    lng = dados.get("lng")

    if lat is None or lng is None:
        return jsonify({"erro": "lat/lng ausentes"}), 400

    motorista_id = session["user_id"]
    conn = get_db()
    conn.execute("""
        INSERT INTO motorista_localizacao (motorista_id, latitude, longitude, atualizado_em)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(motorista_id) DO UPDATE SET
            latitude      = excluded.latitude,
            longitude     = excluded.longitude,
            atualizado_em = excluded.atualizado_em
    """, (motorista_id, lat, lng, datetime.now()))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ─────────────────────────────────────────────
# SCANNER (tela do passageiro)
# ─────────────────────────────────────────────
@app.route("/scanner")
def scanner():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("exibir_qr.html")

# ─────────────────────────────────────────────
# REGISTRAR PRESENÇA (com validação GPS)
# ─────────────────────────────────────────────
@app.route("/registrar", methods=["POST"])
def registrar():
    if "user_id" not in session:
        return jsonify({"status": "erro", "msg": "Faça login primeiro"}), 401

    dados      = request.get_json()
    token      = dados.get("token")
    lat_aluno  = dados.get("lat")
    lng_aluno  = dados.get("lng")

    if not token:
        return jsonify({"status": "erro", "msg": "Token ausente"}), 400

    conn = get_db()

    # 1. Valida token
    qr = conn.execute(
        "SELECT motorista_id, expira_em, usado FROM qr_tokens WHERE token=?",
        (token,)
    ).fetchone()

    if not qr:
        conn.close()
        return jsonify({"status": "erro", "msg": "QR Code inválido"}), 400

    if qr["usado"]:
        conn.close()
        return jsonify({"status": "erro", "msg": "QR Code já utilizado"}), 400

    if datetime.now() > datetime.fromisoformat(qr["expira_em"]):
        conn.close()
        return jsonify({"status": "erro", "msg": "QR Code expirado. Peça ao motorista para atualizar a tela."}), 400

    motorista_id = qr["motorista_id"]

    # 2. Validação de GPS (se coordenadas enviadas)
    lat_motorista = None
    lng_motorista = None
    distancia = None

    if lat_aluno is not None and lng_aluno is not None:
        loc = conn.execute(
            "SELECT latitude, longitude, atualizado_em FROM motorista_localizacao WHERE motorista_id=?",
            (motorista_id,)
        ).fetchone()

        if loc is None:
            conn.close()
            return jsonify({
                "status": "erro",
                "msg": "Localização do motorista não disponível. Motorista deve ativar o GPS na tela dele."
            }), 400

        lat_motorista = loc["latitude"]
        lng_motorista = loc["longitude"]
        distancia = calcular_distancia_metros(lat_aluno, lng_aluno, lat_motorista, lng_motorista)

        if distancia > LIMITE_DISTANCIA_METROS:
            conn.close()
            return jsonify({
                "status": "erro",
                "msg": f"Você está a {int(distancia)} m do ônibus. Aproxime-se para registrar presença.",
                "distancia_m": int(distancia)
            }), 403

    # 3. Marca token como usado (evita reuso)
    conn.execute("UPDATE qr_tokens SET usado=1 WHERE token=?", (token,))

    # 4. Grava presença
    conn.execute("""
        INSERT INTO presencas
            (usuario_id, motorista_id, data_hora,
             lat_aluno, lng_aluno, lat_motorista, lng_motorista, distancia_m)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        session["user_id"], motorista_id, datetime.now(),
        lat_aluno, lng_aluno, lat_motorista, lng_motorista, distancia
    ))

    conn.commit()
    conn.close()

    msg = "Presença registrada com sucesso!"
    if distancia is not None:
        msg += f" (a {int(distancia)} m do ônibus)"

    return jsonify({"status": "ok", "msg": msg})

# ─────────────────────────────────────────────
# SALVAR LOCALIZAÇÃO RESIDENCIAL DO PASSAGEIRO
# ─────────────────────────────────────────────
@app.route("/usuario/salvar_residencia", methods=["POST"])
def salvar_residencia():
    if "user_id" not in session:
        return jsonify({"erro": "Faça login primeiro"}), 401

    dados = request.get_json()
    lat = dados.get("lat")
    lng = dados.get("lng")

    if lat is None or lng is None:
        return jsonify({"erro": "Coordenadas ausentes"}), 400

    conn = get_db()
    conn.execute(
        "UPDATE usuarios SET lat_residencia=?, lng_residencia=? WHERE id=?",
        (lat, lng, session["user_id"])
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "msg": "Localização salva!"})





# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
