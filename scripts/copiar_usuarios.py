from zk import ZK
from zk.exception import ZKErrorConnection

def copiar_usuarios_y_huellas(ip_origen, ip_destino, port=4370):
    usuarios = []
    plantillas = []
    conn = None

    # 1. Obtener datos del reloj origen
    print(f"Conectando a reloj origen ({ip_origen})...")
    zk_origen = ZK(ip_origen, port=port, timeout=10, password=1884)
    try:
        conn = zk_origen.connect()
        conn.disable_device()
        usuarios = conn.get_users()
        plantillas = conn.get_templates()
        print(f"Usuarios obtenidos: {len(usuarios)}")
        print(f"Plantillas de huellas obtenidas: {len(plantillas)}")
        conn.enable_device()
    except Exception as e:
        print(f"Error en reloj origen: {e}")
        return
    finally:
        if conn:
            try:
                conn.disconnect()
            except ZKErrorConnection:
                pass

    # 2. Pisar todo en el reloj destino
    print(f"\nConectando a reloj destino ({ip_destino})...")
    conn = None
    zk_destino = ZK(ip_destino, port=port, timeout=60, password=0)
    try:
        conn = zk_destino.connect()
        conn.disable_device()

        for user in usuarios:
            huellas_usuario = [t for t in plantillas if t.uid == user.uid]
            conn.save_user_template(user, huellas_usuario)
            print(f"  Copiado: '{user.name}' (uid: {user.uid}) - huellas: {len(huellas_usuario)}")

        conn.refresh_data()
        conn.enable_device()
        print("\nCopia completada exitosamente.")

    except Exception as e:
        print(f"Error en reloj destino: {e}")
    finally:
        if conn:
            try:
                conn.disconnect()
            except ZKErrorConnection:
                pass


copiar_usuarios_y_huellas('192.168.0.22', '192.168.0.23')