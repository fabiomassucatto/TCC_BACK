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
        nome varchar(100) not null,
        email varchar(100) UNIQUE,
        senha varchar(100) not null,
        ponto varchar(100) not null,
        tipo varchar(20) not null
    )
    """)

    conn.execute("""
                 CREATE TABLE IF NOT EXISTS presencas (
                 id integer PRIMARY KEY AUTOINCREMENT,
                    usuario_id integer,
                    motorista_id integer,
                    data_hora datetime,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                    FOREIGN KEY (motorista_id) REFERENCES usuarios(id)
                 )""")

    conn.close()

criar_tabela()


@app.route("/")
def index():
    return render_template("usuario.html")

@app.route("/perfil")
def perfil():
    return redirect("/")

# LOGIN Pagina 
@app.route("/login", methods=["GET", "POST"])
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
            session["user"] = user[1] # Salva o nome
            session["user_id"] = user[0]  # Salva o ID
            session["user_tipo"] = user[5] # Salva o tipo
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
        tipo = request.form["tipo"]

        conn = get_db()
        conn.execute(
            "INSERT INTO usuarios (nome, email, senha, ponto, tipo) VALUES (?, ?, ?, ?, ?)",
            (nome, email, senha, ponto, tipo)
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

    if "user_id" not in session:
        return {
            "status": "erro",
            "msg": "Logue primeiro"
        }, 401

    usuario_id = session["user_id"]

    motorista_id = request.json["qr"]

    data_hora = datetime.now()

    conn = get_db()

    conn.execute("""
        INSERT INTO presencas
        (usuario_id, motorista_id, data_hora)
        VALUES (?, ?, ?)
    """, (usuario_id, motorista_id, data_hora))

    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "msg": "Presença registrada"
    }



@app.route("/gerar_qr/<int:motorista_id>")
def gerar_qr(motorista_id):
    # Gerar QR Code com o ID do motorista
    qr = qrcode.make(str(motorista_id))
    img_io = io.BytesIO()
    qr.save(img_io, 'PNG')
    img_io.seek(0)

    # Retornar a imagem do QR Code
    return send_file(img_io, mimetype='image/png')


app.run(debug=True)