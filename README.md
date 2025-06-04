# TrimQ - Barber Shop Queue Management System

TrimQ is a lightweight, admin-facing web application designed to manage customer queues in a barbering shop.

## Features

- Customer registration with name, phone number, and service selection
- Real-time queue management
- Barber assignment tracking
- Multi-branch support
- Service and barber management
- Public queue display screen

## Installation

1. Clone the repository
2. Create and activate a virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Create a PostgreSQL database named `trimq`
5. Set up environment variables in `.env` file
6. Initialize database: `flask db upgrade`
7. Run the application: `python run.py`

## Configuration

Edit the `.env` file to set:

- `SECRET_KEY` - Flask secret key
- `DATABASE_URL` - PostgreSQL connection URL
- `ADMIN_USERNAME` - Default admin username
- `ADMIN_PASSWORD` - Default admin password

## Usage

1. Access the application at `http://localhost:5000`
2. Login with admin credentials
3. Add customers, manage queue, and track service progress

## Deployment

For production deployment:

1. Use gunicorn: `gunicorn -w 4 run:app`
2. Set up a reverse proxy with Nginx or Apache
3. Configure HTTPS with Let's Encrypt

## License

MIT