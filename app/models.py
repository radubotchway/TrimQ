from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, assigned, completed
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'))
    branch = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    service = db.relationship('Service', backref='customers')
    barber = db.relationship('Barber', backref='customers')

    def __repr__(self):
        return f'<Customer {self.name}>'

class Barber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Barber {self.name}>'

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer)  # in minutes
    price = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Service {self.name}>'

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Branch {self.name}>'