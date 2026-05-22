#!/usr/bin/env python3
"""
Simple terminal script to create a Firebase Auth user and Firestore profile.

Run from project root:
    python scripts/create_user_cli.py

This script uses the existing `firebase_auth.crear_usuario_empleado` function,
so it will load Firebase Admin credentials from your `.env` via `firebase_config`.
"""

import getpass
import sys

try:
    from firebase_auth import crear_usuario_empleado
except Exception as e:
    print('Error importing firebase_auth module:', e)
    print('Asegúrate de ejecutar este script desde la carpeta del proyecto (app/).')
    sys.exit(1)


def prompt_create_user():
    print('\n== Crear nuevo usuario (Firebase) ==\n')
    nombre = input('Nombre completo: ').strip()
    email = input('Email: ').strip()

    # Password (hidden)
    while True:
        password = getpass.getpass('Contraseña (mínimo 6 caracteres): ')
        password2 = getpass.getpass('Confirmar contraseña: ')
        if password != password2:
            print('Las contraseñas no coinciden. Intenta de nuevo.\n')
            continue
        if len(password) < 6:
            print('La contraseña debe tener al menos 6 caracteres.\n')
            continue
        break

    # Rol
    rol = ''
    while rol not in ('admin', 'empleado'):
        rol = input("Rol ('admin' o 'empleado'): ").strip().lower()

    # Sucursal (si aplica)
    sucursal_id = 'S1'
    if rol == 'empleado':
        sucursal_id = input('Sucursal ID (S1-S4) [S1]: ').strip() or 'S1'
        if sucursal_id not in ('S1', 'S2', 'S3', 'S4'):
            print('Sucursal inválida. Usando S1.')
            sucursal_id = 'S1'
    else:
        # para admin se acepta valor opcional
        sucursal_id = input('Sucursal ID (opcional) [S1]: ').strip() or 'S1'

    print('\nCreando usuario...')
    res = crear_usuario_empleado(email, password, nombre, rol, sucursal_id)

    if res.get('success'):
        print('✅ Usuario creado exitosamente')
        print('UID:', res.get('uid'))
        print('Email:', res.get('email'))
    else:
        print('❌ Error creando usuario:')
        print(res.get('error'))


if __name__ == '__main__':
    prompt_create_user()
