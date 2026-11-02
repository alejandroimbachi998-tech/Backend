import mysql.connector

def conectar():
    conexion = mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password="23julio2008",
        database="Backend2"
    )

    return conexion


if __name__ == "__main__":
    conexion = conectar()
    print("Conexión exitosa a MySQL")

    conexion.close()