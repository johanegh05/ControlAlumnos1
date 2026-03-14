from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
# Habilitar CORS para permitir peticiones desde tu HTML
CORS(app) 

# Configuración de tu conexión a MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',          # Reemplaza si usas otro usuario
    'password': 'ProyectoSon25GMG',  # PON AQUÍ TU CONTRASEÑA DE MYSQL
    'database': 'control_alumnos'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ---------------------------------------------------------
# RUTA 1: INICIAR SESIÓN / REGISTRAR CLUB
# ---------------------------------------------------------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verificar si el club ya existe
    cursor.execute("SELECT * FROM clubes WHERE id_club = %s", (data['id_unico'],))
    club = cursor.fetchone()
    
    # Si no existe, lo registramos en la base de datos
    if not club:
        cursor.execute(
            "INSERT INTO clubes (id_club, nombre_admin, apellido_admin, nombre_club) VALUES (%s, %s, %s, %s)",
            (data['id_unico'], data['nombre'], data['apellido'], data['club'])
        )
        conn.commit()
    
    cursor.close()
    conn.close()
    return jsonify({"status": "success", "message": "Sesión iniciada correctamente"})

# ---------------------------------------------------------
# RUTA 2: CARGAR DATOS A LA APP WEB (GET)
# ---------------------------------------------------------
@app.route('/api/data/<id_club>', methods=['GET'])
def get_data(id_club):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Obtener Alumnos
    cursor.execute("SELECT * FROM alumnos WHERE id_club = %s", (id_club,))
    alumnos_raw = cursor.fetchall()
    
    # Adaptar formato de alumnos para el JavaScript
    alumnos = []
    clases_set = set()
    for a in alumnos_raw:
        alumnos.append({
            "id": a['id_alumno'],
            "name": a['nombre_completo'],
            "class": a['clase'],
            "attendance": a['asistencias'],
            "participation": a['puntos']
        })
        clases_set.add(a['clase'])

    # 2. Obtener Eventos y sus pagos
    cursor.execute("SELECT * FROM eventos WHERE id_club = %s", (id_club,))
    eventos_raw = cursor.fetchall()
    
    eventos = []
    for e in eventos_raw:
        evento_obj = {
            "id": e['id_evento'],
            "name": e['nombre_evento'],
            "attendees": {}
        }
        
        # Obtener los asistentes de este evento
        cursor.execute("SELECT * FROM pagos_asistencias WHERE id_evento = %s", (e['id_evento'],))
        pagos = cursor.fetchall()
        for p in pagos:
            evento_obj["attendees"][str(p['id_alumno'])] = {
                "attending": bool(p['asistira']),
                "payment": float(p['monto_abonado'])
            }
        
        eventos.append(evento_obj)
        
    cursor.close()
    conn.close()
    
    # Devolver la estructura exacta que tu JS espera
    return jsonify({
        "classes": list(clases_set),
        "students": alumnos,
        "events": eventos
    })

# ---------------------------------------------------------
# RUTA 3: GUARDAR TODO DESDE LA APP WEB (POST)
# ---------------------------------------------------------
@app.route('/api/data', methods=['POST'])
def save_data():
    data = request.json
    id_club = data.get('id_club')
    db_json = data.get('db') # La estructura completa de tu JS
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Guardar Alumnos (Usamos REPLACE o INSERT ON DUPLICATE KEY para actualizar)
        for s in db_json['students']:
            cursor.execute("""
                INSERT INTO alumnos (id_alumno, id_club, nombre_completo, clase, asistencias, puntos) 
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                nombre_completo=VALUES(nombre_completo), clase=VALUES(clase), asistencias=VALUES(asistencias), puntos=VALUES(puntos)
            """, (s['id'], id_club, s['name'], s['class'], s['attendance'], s['participation']))
        
        # Guardar Eventos y Pagos
        for e in db_json['events']:
            cursor.execute("""
                INSERT INTO eventos (id_evento, id_club, nombre_evento) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE nombre_evento=VALUES(nombre_evento)
            """, (e['id'], id_club, e['name']))
            
            # Guardar los pagos/asistencias de cada alumno en este evento
            for id_alumno_str, info in e['attendees'].items():
                id_alumno = int(id_alumno_str)
                cursor.execute("""
                    INSERT INTO pagos_asistencias (id_evento, id_alumno, asistira, monto_abonado)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE asistira=VALUES(asistira), monto_abonado=VALUES(monto_abonado)
                """, (e['id'], id_alumno, info['attending'], info['payment']))

        conn.commit()
    except Exception as err:
        conn.rollback()
        return jsonify({"status": "error", "message": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify({"status": "success"})

if __name__ == '__main__':
    # Arranca el servidor local en el puerto 5000
    app.run(debug=True, port=5000)