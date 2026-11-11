# 🍰 Suspiro Sureño 2.0 — Proyecto B

Sistema web de gestión para una pastelería, desarrollado con **Python y Django** como parte de un proyecto académico de Ingeniería en Informática.

La aplicación permite presentar productos de repostería mediante un catálogo público y gestionar información relacionada con clientes, cotizaciones, pedidos e inventario.

## 🌐 Enlaces del proyecto

- **Página web:** https://suspiro-sureno-django.vercel.app/
- **Catálogo:** https://suspiro-sureno-django.vercel.app/catalogo/
- **Django Admin:** https://suspiro-sureno-django.vercel.app/admin/
- **Repositorio:** https://github.com/Nubby01/suspiro-sureno-django

## 🎯 Objetivo

Desarrollar una plataforma web que contribuya a digitalizar y organizar los procesos de una pastelería, facilitando la presentación de productos, la gestión de cotizaciones y pedidos, y el control de insumos.

## 🛠️ Tecnologías utilizadas

| Tecnología | Uso |
|---|---|
| Python | Lenguaje de programación |
| Django 5.2 LTS | Framework backend |
| HTML y CSS | Estructura y presentación |
| SQLite | Base de datos de desarrollo local |
| PostgreSQL | Base de datos de producción |
| Neon | Alojamiento de PostgreSQL |
| Vercel | Despliegue de la aplicación |
| Git y GitHub | Control de versiones |

## ✨ Funcionalidades principales

### Catálogo de productos

- Visualización pública de productos.
- Organización por categorías.
- Variantes y precios de productos.
- Productos activos e inactivos.
- Visualización de precios pendientes como «Consultar precio».

### Usuarios y autenticación

- Registro de clientes.
- Inicio y cierre de sesión.
- Administración de cuentas.
- Acceso a funcionalidades según los permisos implementados.

### Cotizaciones

- Registro de cotizaciones.
- Asociación de productos y cantidades.
- Consulta de información y estados.

### Pedidos

- Gestión de pedidos.
- Registro de productos asociados.
- Seguimiento mediante eventos del pedido.

### Inventario

- Registro de insumos.
- Movimientos de inventario.
- Recetas e ingredientes.
- Registro de consumo de insumos asociado a pedidos.

### Administración

El sistema dispone de Django Admin y funcionalidades administrativas propias del proyecto para gestionar los registros según los permisos correspondientes.

Los permisos específicos del rol ayudante y algunas reglas operativas requieren validación y pruebas adicionales.

## 📁 Estructura general

```text
suspiro-sureno-django/
├── apps/
│   ├── catalogo/
│   ├── cuentas/
│   ├── cotizaciones/
│   ├── inventario/
│   └── pedidos/
├── config/
├── static/
├── manage.py
├── requirements.txt
├── vercel.json
└── .python-version
```

## 💻 Instalación local

### 1. Clonar el repositorio

```bash
git clone https://github.com/Nubby01/suspiro-sureno-django.git
cd suspiro-sureno-django
```

### 2. Crear el entorno virtual

```powershell
py -3.12 -m venv .venv
```

### 3. Activar el entorno virtual

En Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Instalar las dependencias

```bash
pip install -r requirements.txt
```

### 5. Configurar la base de datos

El proyecto utiliza SQLite para desarrollo local y PostgreSQL en Neon para producción.

Las credenciales de producción se configuran mediante variables de entorno y no deben incorporarse al repositorio.

Para trabajar localmente con SQLite, asegúrate de que no exista una configuración activa que apunte a Neon de producción.

### 6. Aplicar las migraciones

```bash
python manage.py migrate
```

### 7. Crear un superusuario local

```bash
python manage.py createsuperuser
```

### 8. Iniciar el servidor

```bash
python manage.py runserver
```

La aplicación estará disponible en:

http://127.0.0.1:8000/

El administrador local estará disponible en:

http://127.0.0.1:8000/admin/

## ☁️ Despliegue

La aplicación está desplegada en Vercel y utiliza PostgreSQL alojado en Neon.

La configuración de producción contempla las siguientes variables:

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL |
| `DJANGO_SECRET_KEY` | Clave secreta de Django |
| `DJANGO_DEBUG` | Configuración del modo depuración |
| `DJANGO_ALLOWED_HOSTS` | Dominios autorizados |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS autorizados |
| `DJANGO_LOAD_ENV` | Control de carga de variables locales |

Las contraseñas, claves secretas y cadenas de conexión no deben publicarse en GitHub.

## 🗃️ Datos de demostración

La base de datos desplegada contiene información ficticia para demostrar el funcionamiento de la aplicación.

Incluye:

- 7 usuarios, incluido un administrador.
- 7 categorías.
- 27 productos.
- 35 variantes.
- 10 insumos.
- 8 cotizaciones.
- 6 pedidos.
- Recetas, movimientos de inventario y eventos asociados.

Estos registros no corresponden a operaciones comerciales reales.

## 🔒 Seguridad

- Uso de variables de entorno para datos sensibles.
- Autenticación de usuarios mediante Django.
- Acceso administrativo restringido.
- Protección CSRF de Django.
- Separación entre las bases de datos de desarrollo y producción.

Los archivos de respaldo, exportaciones de datos y credenciales deben mantenerse fuera del repositorio público.

## 📌 Estado del proyecto

**Aplicación desplegada y operativa para demostración académica.**

Se ha verificado el acceso administrativo desde Vercel, la conexión con Neon y la importación de los datos de demostración.

Quedan pendientes de comprobación final los permisos de los distintos roles, algunos flujos administrativos y la información de contacto del sitio.

## 🎓 Contexto académico

Suspiro Sureño 2.0 — Proyecto B forma parte de un trabajo académico de Ingeniería en Informática.

Esta implementación utiliza Django y mantiene su propio repositorio y base de datos, de manera independiente del Proyecto A.

---

**Suspiro Sureño 2.0 — Proyecto B**

*Tecnología para apoyar la gestión de una pastelería.*
