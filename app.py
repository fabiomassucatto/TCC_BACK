from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)


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


@app.route("/QR_CODE")
def qr_code():
    return render_template("QR_CODE.html")

app.run(debug=True)