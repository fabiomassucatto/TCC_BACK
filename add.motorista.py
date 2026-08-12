import sqlite3

def adicionar_motorista():
    conn = sqlite3.connect("database.db")
    try:
        conn.execute("""
            INSERT INTO usuarios (nome, email, senha, ponto, linha, tipo) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("Carlos Motorista", "carlos@onibus.com", "senha123", "Garagem Central", "Linha 1", "motorista"))
        conn.commit()
        print("✅ Motorista adicionado com sucesso!")
    except sqlite3.IntegrityError:
        print("❌ Erro: Este e-mail já está cadastrado.")
    finally:
        conn.close()

if __name__ == "__main__":
    adicionar_motorista()