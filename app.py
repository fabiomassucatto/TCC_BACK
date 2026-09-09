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

QR_VALIDADE_SEGUNDOS    = 20
LIMITE_DISTANCIA_METROS = 100

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def criar_tabelas():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nome           VARCHAR(100) NOT NULL,
            email          VARCHAR(100) UNIQUE,
            senha          VARCHAR(100) NOT NULL,
            ponto          VARCHAR(100) NOT NULL,
            linha          VARCHAR(50)  NOT NULL DEFAULT 'Linha 1',
            tipo           VARCHAR(20)  NOT NULL,
            lat_residencia REAL,
            lng_residencia REAL
        )
    """)
    for col, tipo in [("lat_residencia","REAL"),("lng_residencia","REAL"),("linha","VARCHAR(50)")]:
        try: conn.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
        except: pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS presencas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id   INTEGER,
            motorista_id INTEGER,
            data_hora    DATETIME,
            lat_aluno    REAL, lng_aluno    REAL,
            lat_motorista REAL, lng_motorista REAL,
            distancia_m  REAL,
            FOREIGN KEY (usuario_id)   REFERENCES usuarios(id),
            FOREIGN KEY (motorista_id) REFERENCES usuarios(id)
        )
    """)
    for col, tipo in [("lat_aluno","REAL"),("lng_aluno","REAL"),
                      ("lat_motorista","REAL"),("lng_motorista","REAL"),("distancia_m","REAL")]:
        try: conn.execute(f"ALTER TABLE presencas ADD COLUMN {col} {tipo}")
        except: pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS qr_tokens (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            motorista_id INTEGER,
            token        TEXT UNIQUE,
            criado_em    DATETIME,
            expira_em    DATETIME,
            usado        INTEGER DEFAULT 0,
            FOREIGN KEY (motorista_id) REFERENCES usuarios(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS motorista_localizacao (
            motorista_id  INTEGER PRIMARY KEY,
            latitude      REAL,
            longitude     REAL,
            atualizado_em DATETIME,
            FOREIGN KEY (motorista_id) REFERENCES usuarios(id)
        )
    """)
    conn.commit()
    conn.close()

criar_tabelas()

def calcular_distancia_metros(lat1, lng1, lat2, lng2):
    R = 6_371_000
    f1, f2 = radians(lat1), radians(lat2)
    df, dl = radians(lat2-lat1), radians(lng2-lng1)
    a = sin(df/2)**2 + cos(f1)*cos(f2)*sin(dl/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

# ── Rotas gerais ────────────────────────────────────────────────
@app.route("/")
def index(): return redirect("/login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ── Login ────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    erro = None
    if request.method == "POST":
        email     = request.form["email"]
        senha     = request.form["senha"]
        tipo_form = request.form.get("tipo","usuario")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE email=? AND senha=?", (email, senha)
        ).fetchone()
        conn.close()
        if user:
            if user["tipo"] != tipo_form:
                erro = "Perfil incorreto para este usuário."
            else:
                session["user"]      = user["nome"]
                session["user_id"]   = user["id"]
                session["user_tipo"] = user["tipo"]
                return redirect("/dashboard" if user["tipo"] == "motorista" else "/usuario")
        else:
            erro = "E-mail ou senha incorretos."
    return render_template("login.html", erro=erro)

# ── Cadastro ─────────────────────────────────────────────────────
@app.route("/cadastro", methods=["GET","POST"])
def cadastro():
    erro = None
    if request.method == "POST":
        nome            = request.form["nome"]
        email           = request.form["email"]
        senha           = request.form["senha"]
        confirmar_senha = request.form.get("confirmar_senha","")
        ponto           = request.form["ponto"]
        linha           = request.form.get("linha","Linha 1")

        if senha != confirmar_senha:
            erro = "As senhas não coincidem."
        else:
            try:
                conn = get_db()
                conn.execute(
                    "INSERT INTO usuarios (nome,email,senha,ponto,linha,tipo) VALUES (?,?,?,?,?,?)",
                    (nome, email, senha, ponto, linha, "usuario")
                )
                conn.commit()
                conn.close()
                return redirect("/login")
            except sqlite3.IntegrityError:
                erro = "E-mail já cadastrado."
    return render_template("cadastro.html", erro=erro)

# ── Dashboard motorista ──────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    if session.get("user_tipo") != "motorista":
        return redirect("/login")
    motorista_id = session["user_id"]
    conn = get_db()
    hoje = datetime.now().strftime("%Y-%m-%d")

    presencas = conn.execute("""
        SELECT u.nome, u.linha,
               strftime('%H:%M', p.data_hora) AS hora,
               CAST(p.distancia_m AS INTEGER)  AS distancia_m
        FROM presencas p JOIN usuarios u ON u.id = p.usuario_id
        WHERE p.motorista_id=? AND date(p.data_hora)=?
        ORDER BY p.data_hora DESC
    """, (motorista_id, hoje)).fetchall()

    pontos_mapa = conn.execute("""
        SELECT u.nome, u.ponto, u.linha,
               u.lat_residencia AS lat, u.lng_residencia AS lng
        FROM usuarios u
        WHERE u.tipo='usuario' AND u.lat_residencia IS NOT NULL
    """).fetchall()

    conn.close()
    pontos_unicos = len(set(p["ponto"] for p in presencas))
    return render_template("dashboard.html",
        presencas   =[dict(p) for p in presencas],
        pontos_mapa =[dict(p) for p in pontos_mapa],
        pontos_unicos=pontos_unicos)

# ── Dashboard passageiro ─────────────────────────────────────────
@app.route("/usuario")
def usuario():
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    info = conn.execute(
        "SELECT * FROM usuarios WHERE id=?", (session["user_id"],)
    ).fetchone()

    historico = conn.execute("""
        SELECT strftime('%d/%m/%Y', p.data_hora) AS data,
               strftime('%H:%M',   p.data_hora) AS hora,
               CAST(p.distancia_m AS INTEGER)    AS distancia_m,
               u.nome                            AS motorista
        FROM presencas p JOIN usuarios u ON u.id = p.motorista_id
        WHERE p.usuario_id=?
        ORDER BY p.data_hora DESC LIMIT 10
    """, (session["user_id"],)).fetchall()

    pontos_mapa = conn.execute("""
        SELECT u.nome, u.ponto, u.linha,
               u.lat_residencia AS lat, u.lng_residencia AS lng
        FROM usuarios u
        WHERE u.tipo='usuario' AND u.lat_residencia IS NOT NULL
    """).fetchall()

    conn.close()
    return render_template("usuario.html",
        info      =dict(info),
        historico =[dict(h) for h in historico],
        pontos_mapa=[dict(p) for p in pontos_mapa])

# ── QR Code dinâmico ────────────────────────────────────────────
@app.route("/motorista/qr_atual")
def qr_atual():
    if session.get("user_tipo") != "motorista":
        return jsonify({"erro":"Acesso negado"}), 403
    motorista_id = session["user_id"]
    token  = secrets.token_urlsafe(16)
    agora  = datetime.now()
    expira = agora + timedelta(seconds=QR_VALIDADE_SEGUNDOS)
    conn = get_db()
    conn.execute(
        "INSERT INTO qr_tokens (motorista_id,token,criado_em,expira_em) VALUES (?,?,?,?)",
        (motorista_id, token, agora, expira)
    )
    conn.commit()
    conn.close()
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/gerar_qr/<int:motorista_id>")
def gerar_qr(motorista_id):
    return redirect("/motorista/qr_atual")

# ── GPS do motorista ─────────────────────────────────────────────
@app.route("/motorista/atualizar_localizacao", methods=["POST"])
def atualizar_localizacao():
    if session.get("user_tipo") != "motorista":
        return jsonify({"erro":"Acesso negado"}), 403
    dados = request.get_json()
    lat, lng = dados.get("lat"), dados.get("lng")
    if lat is None or lng is None:
        return jsonify({"erro":"lat/lng ausentes"}), 400
    conn = get_db()
    conn.execute("""
        INSERT INTO motorista_localizacao (motorista_id,latitude,longitude,atualizado_em)
        VALUES (?,?,?,?)
        ON CONFLICT(motorista_id) DO UPDATE SET
            latitude=excluded.latitude, longitude=excluded.longitude,
            atualizado_em=excluded.atualizado_em
    """, (session["user_id"], lat, lng, datetime.now()))
    conn.commit()
    conn.close()
    return jsonify({"status":"ok"})

# ── Registrar presença ───────────────────────────────────────────
@app.route("/registrar", methods=["POST"])
def registrar():
    if "user_id" not in session:
        return jsonify({"status":"erro","msg":"Faça login primeiro"}), 401
    dados     = request.get_json()
    token     = dados.get("token")
    lat_aluno = dados.get("lat")
    lng_aluno = dados.get("lng")
    if not token:
        return jsonify({"status":"erro","msg":"Token ausente"}), 400

    conn = get_db()
    qr = conn.execute(
        "SELECT motorista_id,expira_em,usado FROM qr_tokens WHERE token=?", (token,)
    ).fetchone()

    if not qr:
        conn.close(); return jsonify({"status":"erro","msg":"QR Code inválido"}), 400
    if qr["usado"]:
        conn.close(); return jsonify({"status":"erro","msg":"QR Code já utilizado"}), 400
    if datetime.now() > datetime.fromisoformat(qr["expira_em"]):
        conn.close(); return jsonify({"status":"erro","msg":"QR Code expirado. Aguarde o motorista atualizar."}), 400

    motorista_id  = qr["motorista_id"]
    lat_motorista = lng_motorista = distancia = None

    if lat_aluno is not None and lng_aluno is not None:
        loc = conn.execute(
            "SELECT latitude,longitude FROM motorista_localizacao WHERE motorista_id=?",
            (motorista_id,)
        ).fetchone()
        if loc is None:
            conn.close()
            return jsonify({"status":"erro","msg":"GPS do motorista indisponível. Peça para o motorista ativar o GPS."}), 400
        lat_motorista, lng_motorista = loc["latitude"], loc["longitude"]
        distancia = calcular_distancia_metros(lat_aluno, lng_aluno, lat_motorista, lng_motorista)
        if distancia > LIMITE_DISTANCIA_METROS:
            conn.close()
            return jsonify({"status":"erro",
                "msg":f"Você está a {int(distancia)} m do ônibus. Aproxime-se e tente novamente.",
                "distancia_m":int(distancia)}), 403

    conn.execute("UPDATE qr_tokens SET usado=1 WHERE token=?", (token,))
    conn.execute("""
        INSERT INTO presencas
            (usuario_id,motorista_id,data_hora,lat_aluno,lng_aluno,lat_motorista,lng_motorista,distancia_m)
        VALUES (?,?,?,?,?,?,?,?)
    """, (session["user_id"], motorista_id, datetime.now(),
          lat_aluno, lng_aluno, lat_motorista, lng_motorista, distancia))
    conn.commit()
    conn.close()

    msg = "Presença registrada com sucesso!"
    if distancia is not None:
        msg += f" Você estava a {int(distancia)} m do ônibus."
    return jsonify({"status":"ok","msg":msg})

# ── Salvar residência ────────────────────────────────────────────
@app.route("/usuario/salvar_residencia", methods=["POST"])
def salvar_residencia():
    if "user_id" not in session:
        return jsonify({"erro":"Faça login primeiro"}), 401
    dados = request.get_json()
    lat, lng = dados.get("lat"), dados.get("lng")
    if lat is None or lng is None:
        return jsonify({"erro":"Coordenadas ausentes"}), 400
    conn = get_db()
    conn.execute(
        "UPDATE usuarios SET lat_residencia=?,lng_residencia=? WHERE id=?",
        (lat, lng, session["user_id"])
    )
    conn.commit()
    conn.close()
    return jsonify({"status":"ok","msg":"Ponto de coleta salvo com sucesso!"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")