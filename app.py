from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField, PasswordField, IntegerField, FloatField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError  # Added ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
from sqlalchemy import func, and_
from sqlalchemy.exc import PendingRollbackError, IntegrityError, SQLAlchemyError  # Added these
import secrets
import os
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import uuid
from PIL import Image
import io
from contextlib import contextmanager  # Added this for db_transaction

load_dotenv()  # Load environment variables from .env file

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trimq_franchise.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/customers'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Email configuration (optional - can be configured later)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'TrimQ System <noreply@trimq.com>')

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add this error handler to your Flask app (add at the top level of app.py)

from sqlalchemy.exc import PendingRollbackError, IntegrityError, SQLAlchemyError

@app.errorhandler(PendingRollbackError)
def handle_pending_rollback_error(e):
    """Handle SQLAlchemy PendingRollbackError"""
    db.session.rollback()
    flash('A database transaction error occurred. Please try your operation again.', 'error')
    return redirect(request.url)

@app.errorhandler(IntegrityError)
def handle_integrity_error(e):
    """Handle SQLAlchemy IntegrityError"""
    db.session.rollback()
    flash('A database constraint error occurred. Please check your data and try again.', 'error')
    return redirect(request.url)

@app.errorhandler(SQLAlchemyError)
def handle_sqlalchemy_error(e):
    """Handle general SQLAlchemy errors"""
    db.session.rollback()
    flash('A database error occurred. Please try again.', 'error')
    return redirect(request.url)

# Database session management context manager
from contextlib import contextmanager

@contextmanager
def db_transaction():
    """Context manager for database transactions with proper error handling"""
    try:
        yield db.session
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Database transaction failed: {e}")
        raise
    finally:
        # Session will be closed by Flask-SQLAlchemy automatically
        pass


# Database initialization with better error handling
def init_database_with_error_handling():
    """Initialize database with proper error handling"""
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            
            # Run migrations
            migrate_database()
            migrate_customer_database()
            
            # Create sample data
            create_sample_data()
            
            # Cleanup expired tokens
            try:
                expired_count = cleanup_expired_resets()
                if expired_count > 0:
                    print(f"Cleaned up {expired_count} expired password reset tokens")
            except Exception as e:
                print(f"Could not clean up expired tokens: {e}")
            
            print("✅ TrimQ System Ready!")
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print("🔧 Trying to recover...")
        
        try:
            # Try to rollback any pending transactions
            db.session.rollback()
            print("✅ Rolled back pending transactions")
        except Exception as rollback_error:
            print(f"❌ Could not rollback: {rollback_error}")
        
        raise

# Fixed form validation in the template context
def validate_form_data(form_data):
    """Validate form data before processing"""
    errors = []
    
    if not form_data.get('name', '').strip():
        errors.append("Customer name is required")
    
    if not form_data.get('phone', '').strip():
        errors.append("Phone number is required")
    
    service_id = form_data.get('service_id')
    if not service_id or service_id == '0':
        errors.append("Please select a service")
    else:
        try:
            service_id = int(service_id)
            service = Service.query.filter_by(id=service_id, is_active=True).first()
            if not service:
                errors.append("Selected service is not available")
        except (ValueError, TypeError):
            errors.append("Invalid service selection")
    
    return errors

# Usage example in routes:
"""
@app.route('/add/<branch_code>', methods=['GET', 'POST'])
@login_required
def add_customer_with_better_handling(branch_code=None):
    if not branch_code:
        branch_code = current_user.branch
    
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    form = CustomerFormFixed()
    
    if form.validate_on_submit():
        # Validate form data first
        validation_errors = validate_form_data(request.form)
        if validation_errors:
            for error in validation_errors:
                flash(error, 'error')
            return render_template('add_customer.html', 
                                form=form, 
                                branch_code=branch_code, 
                                branch_info=get_branches_dict().get(branch_code, {}))
        
        try:
            with db_transaction():
                # Get or create customer
                customer, is_new = get_or_create_customer_fixed(
                    phone=form.phone.data.strip(),
                    name=form.name.data.strip()
                )
                
                # Add to queue
                customer.add_to_queue(
                    service_id=int(form.service_id.data),
                    branch_code=branch_code,
                    notes=form.notes.data.strip() if form.notes.data else None
                )
                
                # Create visit record
                visit = CustomerVisit(
                    customer_id=customer.id,
                    service_id=customer.service_id,
                    branch=branch_code,
                    notes=customer.notes
                )
                db.session.add(visit)
                
                success_message = f'{customer.name} added to queue!'
                if is_new:
                    success_message += ' (New customer created)'
                
                flash(success_message, 'success')
                
                # Handle ticket printing
                if request.form.get('print_ticket'):
                    return redirect(url_for('print_ticket', customer_id=customer.id))
                else:
                    return redirect(url_for('add_customer', 
                                          branch_code=branch_code, 
                                          customer_added='true', 
                                          customer_id=customer.id))
                                          
        except ValueError as ve:
            flash(str(ve), 'error')
        except Exception as e:
            print(f"Unexpected error in add_customer: {e}")
            flash('An unexpected error occurred. Please try again.', 'error')
    
    # Handle validation errors
    elif form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", 'error')
    
    branches_dict = get_branches_dict()
    return render_template('add_customer.html', 
                         form=form, 
                         branch_code=branch_code, 
                         branch_info=branches_dict.get(branch_code, {}))
"""


# ============================================================================
# MODELS
# ============================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    branch = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='branch_admin')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_master_admin(self):
        return self.role == 'master_admin'
    
    def is_branch_admin(self):
        return self.role == 'branch_admin'

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer)
    price = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)

class Barber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, index=True)  # Added index for faster lookups
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    photo_filename = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text)
    
    # Queue-specific fields (for current visit)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    status = db.Column(db.String(20), default='registered')  # registered, waiting, assigned, completed
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'), nullable=True)
    branch = db.Column(db.String(100), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # First registration
    last_visit = db.Column(db.DateTime, nullable=True)  # Last visit date
    assigned_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Customer metrics
    total_visits = db.Column(db.Integer, default=0)
    
    # Relationships
    service = db.relationship('Service', backref='customers')
    barber = db.relationship('Barber', backref='customers')
    
    def __repr__(self):
        return f'<Customer {self.name}>'
    
    def get_photo_url(self):
        """Get the URL for customer photo"""
        if self.photo_filename:
            return f'/static/uploads/customers/{self.photo_filename}'
        return None
    
    def add_to_queue(self, service_id, branch_code, notes=None):
        """Add this customer to the queue for a service with comprehensive validation"""
        
        # Validate inputs
        if not service_id:
            raise ValueError("Service ID is required")
        
        if not branch_code:
            raise ValueError("Branch code is required")
        
        # Verify the service exists and is active
        service = Service.query.filter_by(id=service_id, is_active=True).first()
        if not service:
            raise ValueError("Invalid service selected or service is not available")
        
        # Verify the branch exists
        branch = Branch.query.filter_by(code=branch_code, is_active=True).first()
        if not branch:
            raise ValueError("Invalid branch selected")
        
        # Check if customer is already in an active queue
        if self.status in ['waiting', 'assigned']:
            if self.branch == branch_code:
                raise ValueError(f"Customer is already in the queue for {branch.name}")
            else:
                # Customer is in queue for different branch
                existing_branch = Branch.query.filter_by(code=self.branch).first()
                existing_branch_name = existing_branch.name if existing_branch else self.branch
                raise ValueError(f"Customer is currently in queue for {existing_branch_name}. Please complete or cancel that service first.")
        
        # Set queue information
        self.service_id = service_id
        self.branch = branch_code
        self.status = 'waiting'
        self.notes = notes
        self.last_visit = datetime.utcnow()
        self.total_visits += 1
        
        # Clear any previous assignment data
        self.barber_id = None
        self.assigned_at = None
        self.completed_at = None

# Added a new model for customer visit history
class CustomerVisit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'), nullable=True)
    branch = db.Column(db.String(100), nullable=False)
    
    visit_date = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    price_paid = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text)
    
    # Relationships
    customer = db.relationship('Customer', backref='visit_history')
    service = db.relationship('Service')
    barber = db.relationship('Barber')

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref='password_resets')
    
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self):
        return not self.used and not self.is_expired()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ============================================================================
# FORMS
# ============================================================================

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class CustomerForm(FlaskForm):
    name = StringField('Customer Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    service_id = SelectField('Select Service', coerce=int, validators=[DataRequired(message="Please select a service")])
    notes = TextAreaField('Special Notes (Optional)')
    submit = SubmitField('Add to Queue')

    def __init__(self, *args, **kwargs):
        super(CustomerForm, self).__init__(*args, **kwargs)
        try:
            services = Service.query.filter_by(is_active=True).order_by('name').all()
            # Add a default empty option that will force validation
            self.service_id.choices = [(0, "Choose a service...")] + [(s.id, f"{s.name} ({s.duration} min • GH₵{s.price:.0f})") for s in services]
        except Exception as e:
            print(f"Error loading services: {e}")
            self.service_id.choices = [(0, "Error loading services")]
    
    def validate_service_id(self, field):
        if field.data == 0 or not field.data:
            raise ValidationError('Please select a service.')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(), 
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')

# ============================================================================
# EMAIL FUNCTIONALITY (Optional)
# ============================================================================

def send_password_reset_email(user, token):
    """Send password reset email to user"""
    if not app.config['MAIL_USERNAME']:
        print("Email not configured. Password reset email would be sent to:", user.email)
        return False
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'TrimQ - Password Reset Request'
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = user.email
        
        reset_url = url_for('reset_password', token=token, _external=True)
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #006b3c 0%, #2563eb 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .ghana-flag {{ height: 4px; background: linear-gradient(to right, #ce1126 33%, #ffd700 33%, #ffd700 66%, #006b3c 66%); margin-bottom: 20px; }}
                .content {{ padding: 30px; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #006b3c 0%, #ffd700 100%); color: white; text-decoration: none; padding: 15px 30px; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; border-radius: 0 0 10px 10px; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="ghana-flag"></div>
                    <h1>🇬🇭 TrimQ Password Reset</h1>
                    <p>Professional Queue Management System</p>
                </div>
                <div class="content">
                    <h2>Hello {user.username},</h2>
                    <p>We received a request to reset your password for your TrimQ account.</p>
                    
                    <p>Click the button below to reset your password:</p>
                    <div style="text-align: center;">
                        <a href="{reset_url}" class="button">Reset My Password</a>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong>
                        <ul>
                            <li>This link expires in 1 hour for security</li>
                            <li>If you didn't request this reset, please ignore this email</li>
                            <li>Contact your administrator if you have concerns</li>
                        </ul>
                    </div>
                    
                    <p>If the button doesn't work, copy and paste this link:</p>
                    <p style="word-break: break-all; background: #f8f9fa; padding: 10px; border-radius: 5px;">
                        {reset_url}
                    </p>
                </div>
                <div class="footer">
                    <p><strong>TrimQ Franchise Management System</strong></p>
                    <p>This is an automated message. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        TrimQ Password Reset Request
        
        Hello {user.username},
        
        We received a request to reset your password for your TrimQ account.
        
        Click this link to reset your password:
        {reset_url}
        
        This link expires in 1 hour for security.
        
        If you didn't request this reset, please ignore this email.
        
        TrimQ Franchise Management System
        """
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
            
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_branches_dict():
    """Get branches as a dictionary"""
    branches = Branch.query.all()
    return {
        branch.code: {
            'name': branch.name,
            'address': branch.address,
            'phone': branch.phone
        }
        for branch in branches
    }

def get_wait_time(customer):
    """Calculate estimated wait time"""
    if customer.status != 'waiting':
        return None
    
    earlier_customers = Customer.query.filter(
        Customer.branch == customer.branch,
        Customer.status == 'waiting',
        Customer.created_at < customer.created_at
    ).order_by(Customer.created_at).all()
    
    total_wait = sum(Service.query.get(c.service_id).duration or 0 for c in earlier_customers)
    
    if total_wait == 0:
        return "Up Next!"
    elif total_wait <= 15:
        return f"~{total_wait} min"
    else:
        return f"~{total_wait} min"

def get_branch_stats(branch_code):
    """Get statistics for a branch"""
    waiting = Customer.query.filter_by(branch=branch_code, status='waiting').count()
    in_progress = Customer.query.filter_by(branch=branch_code, status='assigned').count()
    completed_today = Customer.query.filter(
        Customer.branch == branch_code,
        Customer.status == 'completed',
        Customer.completed_at >= datetime.now().replace(hour=0, minute=0, second=0)
    ).count()
    active_barbers = Barber.query.filter_by(branch=branch_code).count()
    
    return {
        'waiting': waiting,
        'in_progress': in_progress,
        'completed_today': completed_today,
        'active_barbers': active_barbers
    }

def get_real_time_revenue_data(target_date=None, branch_code=None):
    """Get real-time revenue data calculated from completed customers"""
    if not target_date:
        target_date = date.today()
    
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time())
    
    query = db.session.query(
        Customer.branch,
        func.sum(Service.price).label('total_revenue'),
        func.count(Customer.id).label('total_customers')
    ).join(Service, Customer.service_id == Service.id).filter(
        Customer.status == 'completed',
        Customer.completed_at >= start_datetime,
        Customer.completed_at <= end_datetime
    )
    
    if branch_code:
        query = query.filter(Customer.branch == branch_code)
    
    revenue_data = query.group_by(Customer.branch).order_by(
        func.sum(Service.price).desc()
    ).all()
    
    result = []
    for record in revenue_data:
        result.append({
            'branch': record.branch,
            'total_revenue': float(record.total_revenue or 0),
            'total_customers': int(record.total_customers or 0),
            'date': target_date,
            'updated_at': datetime.utcnow()
        })
    
    return result

def get_branch_revenue_summary(branch_code, target_date=None):
    """Get revenue summary for a specific branch"""
    if not target_date:
        target_date = date.today()
    
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time())
    
    result = db.session.query(
        func.sum(Service.price).label('total_revenue'),
        func.count(Customer.id).label('total_customers')
    ).join(Service, Customer.service_id == Service.id).filter(
        Customer.branch == branch_code,
        Customer.status == 'completed',
        Customer.completed_at >= start_datetime,
        Customer.completed_at <= end_datetime
    ).first()
    
    return {
        'branch': branch_code,
        'total_revenue': float(result.total_revenue or 0),
        'total_customers': int(result.total_customers or 0),
        'date': target_date,
        'updated_at': datetime.utcnow()
    }

def get_service_breakdown(branch_code=None, target_date=None):
    """Get service-wise revenue breakdown"""
    if not target_date:
        target_date = date.today()
    
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time())
    
    query = db.session.query(
        Service.name,
        Service.price,
        func.count(Customer.id).label('service_count'),
        func.sum(Service.price).label('service_revenue')
    ).join(Customer, Customer.service_id == Service.id).filter(
        Customer.status == 'completed',
        Customer.completed_at >= start_datetime,
        Customer.completed_at <= end_datetime
    )
    
    if branch_code:
        query = query.filter(Customer.branch == branch_code)
    
    return query.group_by(Service.id).order_by(
        func.sum(Service.price).desc()
    ).all()

def get_hourly_revenue_trend(branch_code=None, target_date=None):
    """Get hourly revenue trend for the day"""
    if not target_date:
        target_date = date.today()
    
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time())
    
    query = db.session.query(
        func.extract('hour', Customer.completed_at).label('hour'),
        func.sum(Service.price).label('hour_revenue'),
        func.count(Customer.id).label('hour_customers')
    ).join(Service, Customer.service_id == Service.id).filter(
        Customer.status == 'completed',
        Customer.completed_at >= start_datetime,
        Customer.completed_at <= end_datetime
    )
    
    if branch_code:
        query = query.filter(Customer.branch == branch_code)
    
    return query.group_by(func.extract('hour', Customer.completed_at)).order_by('hour').all()

def generate_ticket_number(customer_id, branch_code):
    """Generate a unique ticket number"""
    today = datetime.now()
    return f"{branch_code.upper()}-{today.strftime('%m%d')}-{customer_id:04d}"

def can_remove_customer(customer):
    """Check if a customer can be removed from the queue"""
    if customer.status == 'completed':
        return False, "Cannot remove completed customers"
    
    if customer.status == 'assigned':
        # Allow cancellation of assigned customers (move back to waiting)
        return True, "Customer will be moved back to waiting queue"
    
    if customer.status == 'waiting':
        return True, "Customer will be removed from queue"
    
    return False, f"Cannot remove customer with status: {customer.status}"

def get_queue_statistics(branch_code):
    """Get comprehensive queue statistics for a branch"""
    stats = {
        'waiting': Customer.query.filter_by(branch=branch_code, status='waiting').count(),
        'in_progress': Customer.query.filter_by(branch=branch_code, status='assigned').count(),
        'completed_today': Customer.query.filter(
            Customer.branch == branch_code,
            Customer.status == 'completed',
            Customer.completed_at >= datetime.now().replace(hour=0, minute=0, second=0)
        ).count(),
        'total_customers': Customer.query.filter_by(branch=branch_code).count(),
        'active_barbers': Barber.query.filter_by(branch=branch_code, is_active=True).count()
    }
    
    # Calculate average wait time
    waiting_customers = Customer.query.filter_by(branch=branch_code, status='waiting').order_by(Customer.created_at).all()
    
    if waiting_customers:
        total_wait_time = 0
        for customer in waiting_customers:
            wait_minutes = (datetime.utcnow() - customer.created_at).total_seconds() / 60
            total_wait_time += wait_minutes
        
        stats['avg_wait_time'] = total_wait_time / len(waiting_customers)
    else:
        stats['avg_wait_time'] = 0
    
    return stats

def log_customer_action(customer_id, action, user_id, details=None):
    """Log customer management actions for audit purposes"""
    # This could be expanded to include a CustomerLog model for audit trails
    print(f"Customer Action Log: User {user_id} performed '{action}' on Customer {customer_id}")
    if details:
        print(f"Details: {details}")

@app.context_processor
def inject_helpers():
    return {
        'now': datetime.now(),
        'get_wait_time': get_wait_time,
        'BRANCHES': get_branches_dict()
    }

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_customer_photo(file, customer_id=None):
    """Save uploaded customer photo and return filename"""
    if file and allowed_file(file.filename):
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        if customer_id:
            filename = f"customer_{customer_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        else:
            filename = f"customer_{uuid.uuid4().hex}.{file_extension}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Resize and save image
        try:
            image = Image.open(file)
            # Resize to max 400x400 while maintaining aspect ratio
            image.thumbnail((400, 400), Image.Resampling.LANCZOS)
            
            # Convert RGBA to RGB if necessary
            if image.mode == 'RGBA':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            
            image.save(filepath, optimize=True, quality=85)
            return filename
        except Exception as e:
            print(f"Error saving image: {e}")
            return None
    return None

def delete_customer_photo(filename):
    """Delete customer photo file"""
    if filename:
        try:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Error deleting photo: {e}")

def get_or_create_customer(phone, name=None, email=None, address=None, photo_file=None):
    """Get existing customer by phone or create new one"""
    customer = Customer.query.filter_by(phone=phone).first()
    
    if customer:
        # Update existing customer info if provided
        if name and name.strip():
            customer.name = name.strip()
        if email and email.strip():
            customer.email = email.strip()
        if address and address.strip():
            customer.address = address.strip()
        
        # Handle photo update
        if photo_file:
            # Delete old photo if exists
            if customer.photo_filename:
                delete_customer_photo(customer.photo_filename)
            
            # Save new photo
            filename = save_customer_photo(photo_file, customer.id)
            if filename:
                customer.photo_filename = filename
        
        return customer, False  # False = not newly created
    else:
        # Create new customer WITHOUT service_id (it will be set in add_to_queue)
        if not name or not name.strip():
            raise ValueError("Name is required for new customers")
        
        customer = Customer(
            name=name.strip(),
            phone=phone.strip(),
            email=email.strip() if email else None,
            address=address.strip() if address else None,
            status='registered'
            # Don't set service_id, branch, or queue-related fields here
        )
        
        db.session.add(customer)
        db.session.flush()  # Get the ID before saving photo
        
        # Handle photo
        if photo_file:
            filename = save_customer_photo(photo_file, customer.id)
            if filename:
                customer.photo_filename = filename
        
        return customer, True  # True = newly created

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('welcome.html')
    
    if current_user.is_master_admin():
        # Master admin dashboard with real-time franchise stats
        branches_dict = get_branches_dict()
        today_date = date.today()
        
        # Get real-time revenue for all branches
        all_revenue_data = get_real_time_revenue_data(today_date)
        branch_revenue = {r['branch']: r for r in all_revenue_data}
        
        branch_stats = {}
        franchise_stats = {
            'total_waiting': 0,
            'total_in_progress': 0,
            'total_completed_today': 0,
            'total_barbers': 0,
            'total_revenue': 0
        }
        
        for code in branches_dict.keys():
            waiting = Customer.query.filter_by(branch=code, status='waiting').count()
            in_progress = Customer.query.filter_by(branch=code, status='assigned').count()
            completed_today = Customer.query.filter(
                Customer.branch == code,
                Customer.status == 'completed',
                Customer.completed_at >= datetime.now().replace(hour=0, minute=0, second=0)
            ).count()
            active_barbers = Barber.query.filter_by(branch=code).count()
            
            # Get real-time revenue
            revenue_info = branch_revenue.get(code, {'total_revenue': 0, 'total_customers': 0})
            
            branch_stats[code] = {
                'waiting': waiting,
                'in_progress': in_progress,
                'completed_today': completed_today,
                'active_barbers': active_barbers,
                'revenue': revenue_info['total_revenue'],
                'revenue_customers': revenue_info['total_customers']
            }
            
            # Add to franchise totals
            franchise_stats['total_waiting'] += waiting
            franchise_stats['total_in_progress'] += in_progress
            franchise_stats['total_completed_today'] += completed_today
            franchise_stats['total_barbers'] += active_barbers
            franchise_stats['total_revenue'] += revenue_info['total_revenue']
        
        return render_template('master_dashboard.html',
                             franchise_stats=franchise_stats,
                             branch_stats=branch_stats)
    else:
        # Branch admin dashboard with real-time branch stats
        branch_stats = get_branch_stats(current_user.branch)
        
        # Add real-time revenue
        revenue_data = get_branch_revenue_summary(current_user.branch)
        branch_stats['revenue'] = revenue_data['total_revenue']
        branch_stats['revenue_customers'] = revenue_data['total_customers']
        
        return render_template('dashboard.html', **branch_stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data, is_active=True).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash(f'Welcome back!', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        
        if user:
            token = secrets.token_urlsafe(32)
            reset_request = PasswordReset(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(reset_request)
            db.session.commit()
            
            if send_password_reset_email(user, token):
                flash('Password reset instructions have been sent to your email.', 'success')
            else:
                flash('Failed to send email. Please contact your administrator.', 'error')
        else:
            flash('If an account with that email exists, password reset instructions have been sent.', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    reset_request = PasswordReset.query.filter_by(token=token).first()
    
    if not reset_request or not reset_request.is_valid():
        flash('Invalid or expired password reset link.', 'error')
        return redirect(url_for('forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = reset_request.user
        user.password = generate_password_hash(form.password.data)
        reset_request.used = True
        db.session.commit()
        
        flash('Your password has been reset successfully. You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', form=form, token=token)

@app.route('/branch/<branch_code>')
@login_required
def branch_view(branch_code):
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    branch_stats = get_branch_stats(branch_code)
    branches_dict = get_branches_dict()
    branch_info = branches_dict.get(branch_code, {})
    
    return render_template('branch_dashboard.html',
                         branch_code=branch_code,
                         branch_info=branch_info,
                         **branch_stats)

@app.route('/add/<branch_code>', methods=['GET', 'POST'])
@login_required
def add_customer(branch_code=None):
    if not branch_code:
        branch_code = current_user.branch
    
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    form = CustomerForm()
    
    # Pre-fill form with query parameters if provided (for existing customers)
    phone = request.args.get('phone', '')
    name = request.args.get('name', '')
    
    if request.method == 'GET' and phone:
        # Try to find existing customer
        existing_customer = Customer.query.filter_by(phone=phone).first()
        if (existing_customer):
            form.name.data = existing_customer.name
            form.phone.data = existing_customer.phone
            flash(f'Found existing customer: {existing_customer.name}', 'info')
        else:
            form.phone.data = phone
            if name:
                form.name.data = name
    
    if form.validate_on_submit():
        try:
            # Validate that service_id is not None or empty
            if not form.service_id.data:
                flash('Please select a service.', 'error')
                return render_template('add_customer.html', 
                                    form=form, 
                                    branch_code=branch_code, 
                                    branch_info=get_branches_dict().get(branch_code, {}))
            
            # Get or create customer
            customer, is_new = get_or_create_customer(
                phone=form.phone.data,
                name=form.name.data
            )
            
            # Check if customer is already in queue for this branch
            if customer.status == 'waiting' and customer.branch == branch_code:
                branches_dict = get_branches_dict()
                branch_name = branches_dict.get(branch_code, {}).get('name', branch_code)
                flash(f'{customer.name} is already in the waiting queue for {branch_name}.', 'warning')
                return render_template('add_customer.html', 
                                    form=form, 
                                    branch_code=branch_code, 
                                    branch_info=branches_dict.get(branch_code, {}))
            
            # Add to queue with proper error handling
            try:
                customer.add_to_queue(form.service_id.data, branch_code, form.notes.data)
                db.session.commit()
                
                # Create visit record
                visit = CustomerVisit(
                    customer_id=customer.id,
                    service_id=form.service_id.data,
                    branch=branch_code,
                    notes=form.notes.data
                )
                db.session.add(visit)
                db.session.commit()
                
                # Log the action
                action = 'added_existing' if not is_new else 'added_new'
                log_customer_action(customer.id, action, current_user.id, {
                    'name': customer.name,
                    'phone': customer.phone,
                    'service': customer.service.name,
                    'branch': branch_code,
                    'is_new_customer': is_new
                })
                
                success_message = f'{customer.name} added to queue!'
                if is_new:
                    success_message += ' (New customer created)'
                
                # Handle ticket printing
                print_ticket_option = request.form.get('print_ticket')
                if print_ticket_option:
                    flash(success_message, 'success')
                    return redirect(url_for('print_ticket', customer_id=customer.id))
                else:
                    flash(success_message, 'success')
                    return redirect(url_for('add_customer', 
                                          branch_code=branch_code, 
                                          customer_added='true', 
                                          customer_id=customer.id))
                                          
            except Exception as db_error:
                # Rollback the transaction to clear the pending rollback state
                db.session.rollback()
                print(f"Database error: {db_error}")
                flash(f'Database error: Could not add customer to queue. Please try again.', 'error')
                
        except ValueError as ve:
            # Handle validation errors
            db.session.rollback()
            flash(str(ve), 'error')
        except Exception as e:
            # Handle any other unexpected errors
            db.session.rollback()
            print(f"Unexpected error in add_customer: {e}")
            flash(f'Error adding customer: Please try again or contact support.', 'error')
    
    branches_dict = get_branches_dict()
    return render_template('add_customer.html', 
                         form=form, 
                         branch_code=branch_code, 
                         branch_info=branches_dict.get(branch_code, {}))


@app.route('/queue/<branch_code>')
@login_required
def queue_manage(branch_code):
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    waiting = Customer.query.filter_by(branch=branch_code, status='waiting').order_by(Customer.created_at).all()
    in_progress = Customer.query.filter_by(branch=branch_code, status='assigned').order_by(Customer.assigned_at).all()
    barbers = Barber.query.filter_by(branch=branch_code).order_by(Barber.name).all()
    
    branches_dict = get_branches_dict()
    return render_template('queue.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         barbers=barbers,
                         branch_code=branch_code,
                         branch_info=branches_dict.get(branch_code, {}))

@app.route('/assign/<int:customer_id>', methods=['POST'])
@login_required
def assign_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    barber_id = request.form.get('barber_id')
    
    if barber_id:
        customer.barber_id = barber_id
        customer.status = 'assigned'
        customer.assigned_at = datetime.utcnow()
        db.session.commit()
        barber = Barber.query.get(barber_id)
        flash(f'{customer.name} assigned to {barber.name}', 'success')
    
    return redirect(url_for('queue_manage', branch_code=customer.branch))

@app.route('/complete/<int:customer_id>')
@login_required
def complete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.status = 'completed'
    customer.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f'{customer.name} service completed! Revenue updated automatically.', 'success')
    return redirect(url_for('queue_manage', branch_code=customer.branch))

@app.route('/display/<branch_code>')
def public_display(branch_code):
    waiting = Customer.query.filter_by(branch=branch_code, status='waiting').order_by(Customer.created_at).all()
    in_progress = Customer.query.filter_by(branch=branch_code, status='assigned').order_by(Customer.assigned_at).all()
    
    branches_dict = get_branches_dict()
    return render_template('display.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         branch_code=branch_code,
                         branch_info=branches_dict.get(branch_code, {}))

@app.route('/ticket/<int:customer_id>')
@login_required
def print_ticket(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    if not current_user.is_master_admin() and current_user.branch != customer.branch:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    ticket_number = generate_ticket_number(customer.id, customer.branch)
    queue_position = Customer.query.filter(
        Customer.branch == customer.branch,
        Customer.status == 'waiting',
        Customer.created_at <= customer.created_at
    ).count()
    
    estimated_wait = get_wait_time(customer)
    branches_dict = get_branches_dict()
    
    return render_template('ticket.html', 
                         customer=customer,
                         ticket_number=ticket_number,
                         queue_position=queue_position,
                         estimated_wait=estimated_wait,
                         branch_info=branches_dict.get(customer.branch, {}))

@app.route('/revenue-report')
@login_required
def revenue_report():
    # Get date from query parameter, default to today
    report_date_str = request.args.get('date')
    if report_date_str:
        try:
            report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
        except ValueError:
            report_date = date.today()
    else:
        report_date = date.today()
    
    # Get real-time revenue data based on user role
    if current_user.is_master_admin():
        revenue_data = get_real_time_revenue_data(report_date)
        service_breakdown = get_service_breakdown(target_date=report_date)
        branches_dict = get_branches_dict()
    else:
        revenue_data = get_real_time_revenue_data(report_date, current_user.branch)
        service_breakdown = get_service_breakdown(current_user.branch, report_date)
        branches_dict = get_branches_dict()
    
    # Calculate totals
    total_revenue = sum(r['total_revenue'] for r in revenue_data)
    total_customers = sum(r['total_customers'] for r in revenue_data)
    
    # Get hourly trends
    if current_user.is_master_admin():
        hourly_trend = get_hourly_revenue_trend(target_date=report_date)
    else:
        hourly_trend = get_hourly_revenue_trend(current_user.branch, report_date)
    
    return render_template('revenue_report.html',
                         revenue_data=revenue_data,
                         service_breakdown=service_breakdown,
                         hourly_trend=hourly_trend,
                         report_date=report_date,
                         total_revenue=total_revenue,
                         total_customers=total_customers,
                         today=date.today(),
                         timedelta=timedelta,
                         branches_dict=branches_dict)

@app.route('/api/revenue/<branch_code>')
@login_required
def api_branch_revenue(branch_code):
    """API endpoint to get real-time revenue for a branch"""
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        return jsonify({'error': 'Access denied'}), 403
    
    today = date.today()
    revenue_data = get_branch_revenue_summary(branch_code, today)
    
    return jsonify({
        'branch': branch_code,
        'date': today.isoformat(),
        'total_revenue': revenue_data['total_revenue'],
        'total_customers': revenue_data['total_customers'],
        'last_updated': revenue_data['updated_at'].isoformat()
    })

@app.route('/api/revenue/all')
@login_required
def api_all_revenue():
    """API endpoint to get real-time revenue for all branches (Master Admin only)"""
    if not current_user.is_master_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    today = date.today()
    revenue_data = get_real_time_revenue_data(today)
    
    # Include branches with zero revenue
    all_branches = get_branches_dict()
    branch_revenue = {r['branch']: r for r in revenue_data}
    
    result = []
    for branch_code in all_branches.keys():
        if branch_code in branch_revenue:
            result.append(branch_revenue[branch_code])
        else:
            result.append({
                'branch': branch_code,
                'total_revenue': 0.0,
                'total_customers': 0,
                'date': today,
                'updated_at': datetime.utcnow()
            })
    
    total_revenue = sum(r['total_revenue'] for r in result)
    total_customers = sum(r['total_customers'] for r in result)
    
    return jsonify({
        'branches': result,
        'totals': {
            'total_revenue': total_revenue,
            'total_customers': total_customers,
            'date': today.isoformat(),
            'last_updated': datetime.utcnow().isoformat()
        }
    })

@app.route('/api/service-breakdown/<branch_code>')
@login_required
def api_service_breakdown(branch_code):
    """API endpoint for service breakdown"""
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        return jsonify({'error': 'Access denied'}), 403
    
    today = date.today()
    breakdown = get_service_breakdown(branch_code if branch_code != 'all' else None, today)
    
    result = []
    for service in breakdown:
        result.append({
            'service_name': service.name,
            'price': float(service.price),
            'count': int(service.service_count),
            'revenue': float(service.service_revenue)
        })
    
    return jsonify({'services': result})

@app.route('/api/hourly-trend/<branch_code>')
@login_required
def api_hourly_trend(branch_code):
    """API endpoint for hourly revenue trend"""
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        return jsonify({'error': 'Access denied'}), 403
    
    today = date.today()
    trend = get_hourly_revenue_trend(branch_code if branch_code != 'all' else None, today)
    
    result = []
    for hour_data in trend:
        result.append({
            'hour': int(hour_data.hour),
            'revenue': float(hour_data.hour_revenue or 0),
            'customers': int(hour_data.hour_customers or 0)
        })
    
    return jsonify({'hourly_data': result})

@app.route('/settings')
@login_required
def settings():
    services = Service.query.order_by(Service.name).all()
    
    if current_user.is_master_admin():
        barbers = Barber.query.order_by(Barber.branch, Barber.name).all()
        branches = Branch.query.order_by(Branch.name).all()
        users = User.query.order_by(User.username).all()
    else:
        barbers = Barber.query.filter_by(branch=current_user.branch).order_by(Barber.name).all()
        branches = []
        users = [current_user]
    
    return render_template('settings.html', 
                         services=services, 
                         barbers=barbers, 
                         branches=branches,
                         users=users)

@app.route('/add_user', methods=['POST'])
@login_required
def add_user():
    if not current_user.is_master_admin():
        flash('Only master admin can add users.', 'error')
        return redirect(url_for('settings'))
    
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower() or None
    password = request.form.get('password', '').strip()
    branch = request.form.get('branch', '').strip()
    role = request.form.get('role', 'branch_admin').strip()
    
    if not username or not password or not branch:
        flash('Username, password, and branch are required.', 'error')
        return redirect(url_for('settings'))
    
    if len(password) < 6:
        flash('Password must be at least 6 characters long.', 'error')
        return redirect(url_for('settings'))
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists. Please choose a different one.', 'error')
        return redirect(url_for('settings'))
    
    if email and User.query.filter_by(email=email).first():
        flash('Email address is already in use.', 'error')
        return redirect(url_for('settings'))
    
    if not Branch.query.filter_by(code=branch).first():
        flash('Invalid branch selected.', 'error')
        return redirect(url_for('settings'))
    
    user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        branch=branch,
        role=role
    )
    
    db.session.add(user)
    db.session.commit()
    flash(f'User "{username}" created successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/edit_user/<int:user_id>', methods=['POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if not current_user.is_master_admin() and current_user.id != user_id:
        flash('You can only edit your own account.', 'error')
        return redirect(url_for('settings'))
    
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower() or None
    branch = request.form.get('branch', '').strip()
    role = request.form.get('role', '').strip()
    
    if not username or not branch:
        flash('Username and branch are required.', 'error')
        return redirect(url_for('settings'))
    
    existing_user = User.query.filter_by(username=username).first()
    if existing_user and existing_user.id != user.id:
        flash('Username already exists. Please choose a different one.', 'error')
        return redirect(url_for('settings'))
    
    if email:
        existing_email = User.query.filter_by(email=email).first()
        if existing_email and existing_email.id != user.id:
            flash('Email address is already in use.', 'error')
            return redirect(url_for('settings'))
    
    user.username = username
    user.email = email
    user.branch = branch
    
    if current_user.is_master_admin() and role:
        user.role = role
    
    db.session.commit()
    flash(f'User "{username}" updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/change_password/<int:user_id>', methods=['POST'])
@login_required
def change_password(user_id):
    user = User.query.get_or_404(user_id)
    
    if not current_user.is_master_admin() and current_user.id != user_id:
        flash('You can only change your own password.', 'error')
        return redirect(url_for('settings'))
    
    current_password = request.form.get('current_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    if current_user.id == user_id and not current_user.is_master_admin():
        if not current_password or not check_password_hash(user.password, current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('settings'))
    
    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'error')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('settings'))
    
    user.password = generate_password_hash(new_password)
    db.session.commit()
    
    flash(f'Password updated successfully for {user.username}!', 'success')
    return redirect(url_for('settings'))

@app.route('/toggle_user/<int:user_id>')
@login_required
def toggle_user(user_id):
    if not current_user.is_master_admin():
        flash('Only master admin can activate/deactivate users.', 'error')
        return redirect(url_for('settings'))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('settings'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = "activated" if user.is_active else "deactivated"
    flash(f'User "{user.username}" has been {status}.', 'success')
    return redirect(url_for('settings'))

@app.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if not current_user.is_master_admin():
        flash('Only master admin can delete users.', 'error')
        return redirect(url_for('settings'))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('settings'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User "{username}" has been deleted permanently.', 'success')
    return redirect(url_for('settings'))

@app.route('/add_service', methods=['POST'])
@login_required
def add_service():
    name = request.form.get('name')
    duration = request.form.get('duration')
    price = request.form.get('price')
    
    if name and duration and price:
        service = Service(name=name, duration=int(duration), price=float(price))
        db.session.add(service)
        db.session.commit()
        flash(f'Service "{name}" added!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/edit_service/<int:service_id>', methods=['POST'])
@login_required
def edit_service(service_id):
    if not current_user.is_master_admin():
        flash('Only master admin can edit services.', 'error')
        return redirect(url_for('settings'))
    
    service = Service.query.get_or_404(service_id)
    name = request.form.get('name')
    duration = request.form.get('duration')
    price = request.form.get('price')
    
    if name and duration and price:
        service.name = name
        service.duration = int(duration)
        service.price = float(price)
        db.session.commit()
        flash(f'Service "{name}" updated!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/delete_service/<int:service_id>')
@login_required
def delete_service(service_id):
    if not current_user.is_master_admin():
        flash('Only master admin can delete services.', 'error')
        return redirect(url_for('settings'))
    
    service = Service.query.get_or_404(service_id)
    
    active_customers = Customer.query.filter_by(service_id=service.id).filter(
        Customer.status.in_(['waiting', 'assigned'])
    ).count()
    
    if active_customers > 0:
        flash(f'Cannot delete service - {active_customers} customers are using it.', 'error')
        return redirect(url_for('settings'))
    
    name = service.name
    db.session.delete(service)
    db.session.commit()
    flash(f'Service "{name}" deleted successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/add_barber', methods=['POST'])
@login_required
def add_barber():
    name = request.form.get('name')
    branch = request.form.get('branch')
    
    if name and branch:
        barber = Barber(name=name, branch=branch)
        db.session.add(barber)
        db.session.commit()
        flash(f'Barber "{name}" added!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/delete_barber/<int:barber_id>')
@login_required
def delete_barber(barber_id):
    if not current_user.is_master_admin():
        flash('Only master admin can delete barbers.', 'error')
        return redirect(url_for('settings'))
    
    barber = Barber.query.get_or_404(barber_id)
    
    active_customers = Customer.query.filter_by(barber_id=barber.id, status='assigned').count()
    if active_customers > 0:
        flash(f'Cannot delete {barber.name} - they have {active_customers} active customer(s).', 'error')
        return redirect(url_for('settings'))
    
    name = barber.name
    db.session.delete(barber)
    db.session.commit()
    flash(f'Barber "{name}" deleted successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/add_branch', methods=['POST'])
@login_required
def add_branch():
    if not current_user.is_master_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('settings'))
    
    code = request.form.get('code', '').lower().strip()
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    phone = request.form.get('phone', '').strip()
    
    if code and name and address:
        if not Branch.query.filter_by(code=code).first():
            branch = Branch(code=code, name=name, address=address, phone=phone)
            db.session.add(branch)
            db.session.commit()
            flash(f'Branch "{name}" added!', 'success')
        else:
            flash('Branch code already exists!', 'error')
    
    return redirect(url_for('settings'))

@app.route('/edit_branch/<int:branch_id>', methods=['POST'])
@login_required
def edit_branch(branch_id):
    if not current_user.is_master_admin():
        flash('Only master admin can edit branches.', 'error')
        return redirect(url_for('settings'))
    
    branch = Branch.query.get_or_404(branch_id)
    name = request.form.get('name')
    address = request.form.get('address')
    phone = request.form.get('phone')
    
    if name and address:
        branch.name = name
        branch.address = address
        branch.phone = phone or ''
        db.session.commit()
        flash(f'Branch "{name}" updated!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/remove/<int:customer_id>')
@login_required
def remove_customer(customer_id):
    """Remove a customer from the queue (for waiting customers only)"""
    customer = Customer.query.get_or_404(customer_id)
    
    # Check if user has permission to manage this branch
    if not current_user.is_master_admin() and current_user.branch != customer.branch:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    # Only allow removal of waiting customers (not in progress or completed)
    if customer.status != 'waiting':
        flash(f'Cannot remove {customer.name} - customer is already {customer.status}.', 'error')
        return redirect(url_for('queue_manage', branch_code=customer.branch))
    
    # Store customer info for the flash message
    customer_name = customer.name
    customer_branch = customer.branch
    
    # Delete the customer record
    db.session.delete(customer)
    db.session.commit()
    
    flash(f'{customer_name} has been removed from the queue.', 'success')
    return redirect(url_for('queue_manage', branch_code=customer_branch))

@app.route('/cancel/<int:customer_id>')
@login_required
def cancel_customer(customer_id):
    """Cancel a customer service (for in-progress customers)"""
    customer = Customer.query.get_or_404(customer_id)
    
    # Check if user has permission to manage this branch
    if not current_user.is_master_admin() and current_user.branch != customer.branch:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    # Only allow cancellation of assigned customers
    if customer.status != 'assigned':
        flash(f'Cannot cancel {customer.name} - customer is {customer.status}.', 'error')
        return redirect(url_for('queue_manage', branch_code=customer.branch))
    
    # Reset customer back to waiting status
    customer.status = 'waiting'
    customer.barber_id = None
    customer.assigned_at = None
    db.session.commit()
    
    flash(f'{customer.name} has been moved back to waiting queue.', 'info')
    return redirect(url_for('queue_manage', branch_code=customer.branch))

@app.route('/api/remove_customer/<int:customer_id>', methods=['DELETE'])
@login_required
def api_remove_customer(customer_id):
    """API endpoint to remove a customer (for AJAX calls)"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        # Check permissions
        if not current_user.is_master_admin() and current_user.branch != customer.branch:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        # Check if customer can be removed
        if customer.status not in ['waiting', 'assigned']:
            return jsonify({
                'success': False, 
                'message': f'Cannot remove {customer.name} - customer service is {customer.status}'
            }), 400
        
        customer_name = customer.name
        
        # Also delete associated visit records to avoid foreign key constraints
        CustomerVisit.query.filter_by(customer_id=customer.id).delete()
        
        # Delete the customer record
        db.session.delete(customer)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{customer_name} has been removed from the queue'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in api_remove_customer: {e}")
        return jsonify({
            'success': False, 
            'message': f'Error removing customer: {str(e)}'
        }), 500

@app.route('/api/check_duplicate/<branch_code>')
@login_required
def check_duplicate_customer(branch_code):
    """Check if a customer with given phone number already exists in queue"""
    phone = request.args.get('phone', '')
    
    if not phone:
        return jsonify({'exists': False})
    
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        return jsonify({'error': 'Access denied'}), 403
    
    existing_customer = Customer.query.filter_by(
        phone=phone,
        branch=branch_code,
        status='waiting'
    ).first()
    
    if existing_customer:
        return jsonify({
            'exists': True,
            'customer': {
                'id': existing_customer.id,
                'name': existing_customer.name,
                'phone': existing_customer.phone,
                'service': existing_customer.service.name,
                'created_at': existing_customer.created_at.strftime('%H:%M'),
                'wait_time': get_wait_time(existing_customer)
            }
        })
    
    return jsonify({'exists': False})

@app.route('/re-add/<branch_code>')
@login_required
def re_add_customer(branch_code):
    """Quick re-add form for customers who were removed by mistake"""
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    # Get customer info from query parameters
    name = request.args.get('name', '')
    phone = request.args.get('phone', '')
    service_name = request.args.get('service', '')
    
    # Try to find the service by name
    service = Service.query.filter_by(name=service_name).first()
    service_id = service.id if service else None
    
    return render_template('add_customer.html',
                         form=CustomerForm(name=name, phone=phone, service_id=service_id),
                         branch_code=branch_code,
                         branch_info=get_branches_dict().get(branch_code, {}),
                         is_re_add=True,
                         original_data={'name': name, 'phone': phone, 'service': service_name})

@app.route('/customers')
@login_required
def manage_customers():
    """Customer database management page"""
    search = request.args.get('search', '').strip()
    branch_filter = request.args.get('branch', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Number of customers per page
    
    # Build base query based on user role
    if current_user.is_master_admin():
        # Master admin can see all customers
        query = Customer.query
        
        # Apply branch filter if specified
        if branch_filter:
            # Filter by customers who have visited the specified branch
            query = query.filter(Customer.branch == branch_filter)
    else:
        # Branch admins can only see customers who have visited their branch
        query = Customer.query.filter(Customer.branch == current_user.branch)
    
    # Apply search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                Customer.name.ilike(search_filter),
                Customer.phone.ilike(search_filter),
                Customer.email.ilike(search_filter)
            )
        )
    
    # Order by most recent activity
    query = query.order_by(
        Customer.last_visit.desc().nullslast(),
        Customer.created_at.desc()
    )
    
    customers = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    # Get branches for filter dropdown (master admin only)
    available_branches = get_branches_dict() if current_user.is_master_admin() else {}
    
    return render_template('customer_management.html',
                         customers=customers,
                         search=search,
                         branch_filter=branch_filter,
                         available_branches=available_branches)

@app.route('/api/customers', methods=['POST'])
@login_required
def api_add_customer():
    """API endpoint to add a new customer"""
    try:
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not name or not phone:
            return jsonify({'success': False, 'message': 'Name and phone are required'}), 400
        
        # Check for existing customer with same phone
        existing = Customer.query.filter_by(phone=phone).first()
        if existing:
            return jsonify({
                'success': False, 
                'message': f'Customer with phone {phone} already exists as "{existing.name}"'
            }), 400
        
        # Handle photo upload
        photo_file = request.files.get('photo')
        
        # Create new customer with current user's branch
        customer = Customer(
            name=name,
            phone=phone,
            email=email if email else None,
            address=address if address else None,
            notes=notes if notes else None,
            status='registered',
            total_visits=0,
            branch=current_user.branch  # Set the branch when creating customer
        )
        
        db.session.add(customer)
        db.session.flush()  # Get the ID
        
        # Handle photo upload
        if photo_file and photo_file.filename:
            filename = save_customer_photo(photo_file, customer.id)
            if filename:
                customer.photo_filename = filename
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Customer "{name}" added successfully',
            'customer_id': customer.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    

@app.route('/api/customers/<int:customer_id>')
@login_required
def api_get_customer(customer_id):
    """API endpoint to get customer details"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        return jsonify({
            'success': True,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'address': customer.address,
                'notes': customer.notes,
                'photo_filename': customer.photo_filename,
                'total_visits': customer.total_visits,
                'last_visit': customer.last_visit.isoformat() if customer.last_visit else None,
                'created_at': customer.created_at.isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/customers/<int:customer_id>', methods=['PUT'])
@login_required
def api_update_customer(customer_id):
    """API endpoint to update customer details"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not name or not phone:
            return jsonify({'success': False, 'message': 'Name and phone are required'}), 400
        
        # Check for phone conflicts
        existing = Customer.query.filter(
            Customer.phone == phone,
            Customer.id != customer.id
        ).first()
        
        if existing:
            return jsonify({
                'success': False, 
                'message': f'Phone number {phone} is already used by "{existing.name}"'
            }), 400
        
        # Update basic info
        customer.name = name
        customer.phone = phone
        customer.email = email if email else None
        customer.address = address if address else None
        customer.notes = notes if notes else None
        
        # Handle photo upload
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            # Delete old photo
            if customer.photo_filename:
                delete_customer_photo(customer.photo_filename)
            
            # Save new photo
            filename = save_customer_photo(photo_file, customer.id)
            if filename:
                customer.photo_filename = filename
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Customer "{name}" updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/customers/<int:customer_id>', methods=['DELETE'])
@login_required
def api_delete_customer(customer_id):
    """API endpoint to delete a customer"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        # Check if customer has active queue entries
        if customer.status in ['waiting', 'assigned']:
            return jsonify({
                'success': False,
                'message': 'Cannot delete customer - they are currently in queue'
            }), 400
        
        customer_name = customer.name
        
        # Delete photo file if exists
        if customer.photo_filename:
            delete_customer_photo(customer.photo_filename)
        
        # Delete customer record
        db.session.delete(customer)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Customer "{customer_name}" deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/customers/search')
@login_required
def api_search_customers():
    """API endpoint to search customers (for autocomplete, etc.)"""
    try:
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit', 10, type=int)
        
        if not query or len(query) < 2:
            return jsonify({'customers': []})
        
        search_filter = f"%{query}%"
        customers = Customer.query.filter(
            db.or_(
                Customer.name.ilike(search_filter),
                Customer.phone.ilike(search_filter)
            )
        ).limit(limit).all()
        
        results = []
        for customer in customers:
            results.append({
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'total_visits': customer.total_visits,
                'last_visit': customer.last_visit.strftime('%Y-%m-%d') if customer.last_visit else None
            })
        
        return jsonify({'customers': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ============================================================================
# UTILITY FUNCTIONS FOR MAINTENANCE
# ============================================================================

def migrate_database():
    """Handle database schema migrations"""
    try:
        with db.engine.connect() as conn:
            result = conn.execute(db.text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'email' not in columns:
                print("Adding email column to user table...")
                conn.execute(db.text("ALTER TABLE user ADD COLUMN email VARCHAR(120) UNIQUE"))
                conn.commit()
                print("✅ Email column added successfully!")
            
            result = conn.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='password_reset'"))
            if not result.fetchone():
                print("Creating password_reset table...")
                PasswordReset.__table__.create(db.engine, checkfirst=True)
                print("✅ Password reset table created successfully!")
                
    except Exception as e:
        print(f"Migration error: {e}")
        print("⚠️  You may need to delete the database file and restart")

def migrate_customer_database():
    """Migrate existing customer data to new schema"""
    try:
        with db.engine.connect() as conn:
            # Check if columns exist and add them if missing
            result = conn.execute(db.text("PRAGMA table_info(customer)"))
            columns = [row[1] for row in result.fetchall()]
            
            migrations = []
            if 'email' not in columns:
                migrations.append("ALTER TABLE customer ADD COLUMN email VARCHAR(120)")
            if 'address' not in columns:
                migrations.append("ALTER TABLE customer ADD COLUMN address TEXT")
            if 'photo_filename' not in columns:
                migrations.append("ALTER TABLE customer ADD COLUMN photo_filename VARCHAR(255)")
            if 'last_visit' not in columns:
                migrations.append("ALTER TABLE customer ADD COLUMN last_visit DATETIME")
            if 'total_visits' not in columns:
                migrations.append("ALTER TABLE customer ADD COLUMN total_visits INTEGER DEFAULT 0")
            
            for migration in migrations:
                try:
                    conn.execute(db.text(migration))
                    conn.commit()
                    print(f"✅ Executed: {migration}")
                except Exception as e:
                    print(f"⚠️  Migration failed: {migration} - {e}")
            
            # Update existing customers
            if migrations:
                conn.execute(db.text("""
                    UPDATE customer 
                    SET total_visits = 1, last_visit = created_at 
                    WHERE total_visits IS NULL OR total_visits = 0
                """))
                conn.commit()
                print("✅ Updated existing customer visit counts")
                
    except Exception as e:
        print(f"Migration error: {e}")

def cleanup_expired_resets():
    """Remove expired password reset tokens"""
    expired = PasswordReset.query.filter(
        PasswordReset.expires_at < datetime.utcnow()
    ).all()
    
    for reset in expired:
        db.session.delete(reset)
    
    db.session.commit()
    return len(expired)

def update_existing_customers_branch():
    """Update existing customers without branch information"""
    try:
        customers_without_branch = Customer.query.filter(
            db.or_(Customer.branch.is_(None), Customer.branch == '')
        ).all()
        
        if customers_without_branch:
            print(f"Found {len(customers_without_branch)} customers without branch information")
            
            # For now, assign them to 'main' branch, but you could implement logic
            # to assign based on their service history or ask admin to assign manually
            for customer in customers_without_branch:
                customer.branch = 'main'  # or prompt for branch assignment
            
            db.session.commit()
            print(f"Updated {len(customers_without_branch)} customer records")
        
    except Exception as e:
        print(f"Error updating customer branches: {e}")
        db.session.rollback()

# ============================================================================
# INITIALIZATION
# ============================================================================

def create_sample_data():
    """Create sample data (no static revenue data)"""
    branches_data = [
        {'code': 'main', 'name': 'Main Branch', 'address': '123 Oxford Street, Osu', 'phone': '0302-123-456'},
        {'code': 'downtown', 'name': 'Downtown Branch', 'address': '45 Kwame Nkrumah Ave, Adabraka', 'phone': '0302-789-012'},
        {'code': 'uptown', 'name': 'East Legon Branch', 'address': '78 Liberation Road, East Legon', 'phone': '0302-345-678'}
    ]
    
    for branch_data in branches_data:
        if not Branch.query.filter_by(code=branch_data['code']).first():
            branch = Branch(**branch_data)
            db.session.add(branch)
    
    services_data = [
        {'name': 'Classic Cut', 'duration': 30, 'price': 50},
        {'name': 'Beard Styling', 'duration': 20, 'price': 35},
        {'name': 'Hot Towel Shave', 'duration': 25, 'price': 40},
        {'name': 'Full Service', 'duration': 60, 'price': 80},
        {'name': 'Quick Trim', 'duration': 15, 'price': 25}
    ]
    
    for service_data in services_data:
        if not Service.query.filter_by(name=service_data['name']).first():
            service = Service(**service_data)
            db.session.add(service)
    
    barbers_data = [
        {'name': 'Kwame Asante', 'branch': 'main'},
        {'name': 'Kofi Mensah', 'branch': 'main'},
        {'name': 'Yaw Boateng', 'branch': 'downtown'},
        {'name': 'Samuel Osei', 'branch': 'downtown'},
        {'name': 'Isaac Adjei', 'branch': 'uptown'},
        {'name': 'Prince Agyemang', 'branch': 'uptown'}
    ]
    
    for barber_data in barbers_data:
        if not Barber.query.filter_by(name=barber_data['name'], branch=barber_data['branch']).first():
            barber = Barber(**barber_data)
            db.session.add(barber)
    
    users_data = [
        {'username': 'master_admin', 'password': 'master123', 'role': 'master_admin', 'branch': 'main', 'email': 'master@trimq.com'},
        {'username': 'main_admin', 'password': 'main123', 'role': 'branch_admin', 'branch': 'main', 'email': 'main@trimq.com'},
        {'username': 'downtown_admin', 'password': 'downtown123', 'role': 'branch_admin', 'branch': 'downtown', 'email': 'downtown@trimq.com'},
        {'username': 'uptown_admin', 'password': 'uptown123', 'role': 'branch_admin', 'branch': 'uptown', 'email': 'uptown@trimq.com'}
    ]
    
    for user_data in users_data:
        try:
            existing_user = User.query.filter_by(username=user_data['username']).first()
            if not existing_user:
                user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    password=generate_password_hash(user_data['password']),
                    role=user_data['role'],
                    branch=user_data['branch']
                )
                db.session.add(user)
            else:
                if not existing_user.email:
                    existing_user.email = user_data['email']
        except Exception as e:
            print(f"Error creating user {user_data['username']}: {e}")
            continue
    
    try:
        db.session.commit()
        print("✅ Sample data created/updated successfully!")
    except Exception as e:
        print(f"Error saving sample data: {e}")
        db.session.rollback()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrate_database()
        migrate_customer_database()  # New customer migration function
        create_sample_data()
        update_existing_customers_branch()

        try:
            expired_count = cleanup_expired_resets()
            if expired_count > 0:
                print(f"Cleaned up {expired_count} expired password reset tokens")
        except Exception as e:
            print(f"Could not clean up expired tokens: {e}")
        
        print("✅ TrimQ System Ready!")
        print("\n📋 Default Login Accounts:")
        print("👑 Master Admin: master_admin / master123")
        print("🏪 Main Branch: main_admin / main123")
        print("🏪 Downtown Branch: downtown_admin / downtown123") 
        print("🏪 East Legon Branch: uptown_admin / uptown123")
        print("\n💰 Real-Time Features:")
        print("🎫 Ticket Generation: Available when adding customers")
        print("📊 Real-Time Revenue: Calculated live from completed services")
        print("⚡ Live Updates: Revenue updates instantly when services complete")
        print("📈 Service Breakdown: Real-time analysis by service type")
        print("🕐 Hourly Trends: Live hourly revenue tracking")
        print("\n🌐 Access: http://127.0.0.1:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)