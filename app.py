import qrcode
import io
import base64
from flask import send_file
from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "123456"


# conectando ao banco
def get_db():
    return sqlite3.connect("database.db")

# criar tabela
def criar_tabela():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome varchar(100),
        email varchar(100) UNIQUE,
        senha varchar(100),
        ponto varchar(100)
    )
    """)

    conn.execute("""
                 CREATE TABLE IF NOT EXISTS presencas (
                 id integer PRIMARY KEY AUTOINCREMENT,
                    usuario_id integer,
                    data_hora datetime,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)    
                 
                 )""")

    conn.close()

criar_tabela()

# LOGIN Pagina inicial 
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE email=? AND senha=?",
            (email, senha)
        ).fetchone()

        if user:
            session["user"] = user[1]
            return redirect("/dashboard")

    return render_template("login.html")

# CADASTRO de usuarios
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]
        ponto = request.form["ponto"]

        conn = get_db()
        conn.execute(
            "INSERT INTO usuarios (nome, email, senha, ponto) VALUES (?, ?, ?, ?)",
            (nome, email, senha, ponto)
        )
        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("cadastro.html")

# DASHBOARD 
@app.route("/dashboard")
def dashboard():
    conn = get_db()
    dados = conn.execute("""
        SELECT ponto, COUNT(*) as total
        FROM usuarios
        GROUP BY ponto
    """).fetchall()

    return render_template("dashboard.html", dados=dados)

from datetime import datetime

@app.route("/registrar", methods=["POST"])
def registrar():
    if "user" not in session:
        return {"status": "erro", "msg": "Logue primeiro"}, 401

    ponto_id = request.json["qr"] # ID que veio do QR Code na parede
    nome_usuario = session["user"] # Nome do cara que está logado

    # Aqui você faria um SELECT para pegar o ID do usuario pelo nome 
    # ou salvaria o ID direto na sessão no momento do login.

    # ... salva no banco ...

    return {"status": "ok"}


@app.route("/gerar_qr/<int:id_ponto>")
def gerar_qr(id_ponto):
    # Aqui o QR Code vai conter apenas o ID (ex: "1")
    # que é o que sua rota /registrar espera receber no JSON
    img = qrcode.make(str(id_ponto))
    
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    
    return send_file(buf, mimetype='image/png')

app.run(debug=True)