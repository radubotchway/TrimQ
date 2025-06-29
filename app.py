from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField, PasswordField, IntegerField, FloatField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
import os

load_dotenv()  # Load environment variables from .env file


# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trimq_franchise.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration (optional - can be configured later)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')  # Set via environment variable
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # Set via environment variable
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'TrimQ System <noreply@trimq.com>')

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
    phone = db.Column(db.String(20), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    status = db.Column(db.String(20), default='waiting')
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'))
    branch = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    service = db.relationship('Service', backref='customers')
    barber = db.relationship('Barber', backref='customers')

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
    service_id = SelectField('Select Service', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Special Notes (Optional)')
    submit = SubmitField('Add to Queue')

    def __init__(self, *args, **kwargs):
        super(CustomerForm, self).__init__(*args, **kwargs)
        services = Service.query.order_by('name').all()
        self.service_id.choices = [(s.id, f"{s.name} ({s.duration} min • GH₵{s.price:.0f})") for s in services]

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
    # Check if email is configured
    if not app.config['MAIL_USERNAME']:
        print("Email not configured. Password reset email would be sent to:", user.email)
        return False
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'TrimQ - Password Reset Request'
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = user.email
        
        # Create reset URL
        reset_url = url_for('reset_password', token=token, _external=True)
        
        # HTML email template
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
        
        # Plain text version
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
        
        # Attach parts
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
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

@app.context_processor
def inject_helpers():
    return {
        'now': datetime.now(),
        'get_wait_time': get_wait_time,
        'BRANCHES': get_branches_dict()
    }

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('welcome.html')
    
    if current_user.is_master_admin():
        # Master admin dashboard
        branches_dict = get_branches_dict()
        branch_stats = {code: get_branch_stats(code) for code in branches_dict.keys()}
        franchise_stats = {
            'total_waiting': sum(stats['waiting'] for stats in branch_stats.values()),
            'total_in_progress': sum(stats['in_progress'] for stats in branch_stats.values()),
            'total_completed_today': sum(stats['completed_today'] for stats in branch_stats.values()),
            'total_barbers': sum(stats['active_barbers'] for stats in branch_stats.values())
        }
        return render_template('master_dashboard.html',
                             franchise_stats=franchise_stats,
                             branch_stats=branch_stats)
    else:
        # Branch admin dashboard
        branch_stats = get_branch_stats(current_user.branch)
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
            # Generate secure token
            token = secrets.token_urlsafe(32)
            
            # Create password reset record
            reset_request = PasswordReset(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
            )
            db.session.add(reset_request)
            db.session.commit()
            
            # Send email
            if send_password_reset_email(user, token):
                flash('Password reset instructions have been sent to your email.', 'success')
            else:
                flash('Failed to send email. Please contact your administrator.', 'error')
        else:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists, password reset instructions have been sent.', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # Find valid reset request
    reset_request = PasswordReset.query.filter_by(token=token).first()
    
    if not reset_request or not reset_request.is_valid():
        flash('Invalid or expired password reset link.', 'error')
        return redirect(url_for('forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Update user password
        user = reset_request.user
        user.password = generate_password_hash(form.password.data)
        
        # Mark reset request as used
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
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            phone=form.phone.data,
            service_id=form.service_id.data,
            branch=branch_code,
            notes=form.notes.data
        )
        db.session.add(customer)
        db.session.commit()
        flash(f'{customer.name} added to queue!', 'success')
        return redirect(url_for('queue_manage', branch_code=branch_code))
    
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
    flash(f'{customer.name} service completed!', 'success')
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
        users = [current_user]  # Only show their own account
    
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
    
    # Validation
    if not username or not password or not branch:
        flash('Username, password, and branch are required.', 'error')
        return redirect(url_for('settings'))
    
    if len(password) < 6:
        flash('Password must be at least 6 characters long.', 'error')
        return redirect(url_for('settings'))
    
    # Check if username already exists
    if User.query.filter_by(username=username).first():
        flash('Username already exists. Please choose a different one.', 'error')
        return redirect(url_for('settings'))
    
    # Check if email is already taken
    if email and User.query.filter_by(email=email).first():
        flash('Email address is already in use.', 'error')
        return redirect(url_for('settings'))
    
    # Validate branch exists
    if not Branch.query.filter_by(code=branch).first():
        flash('Invalid branch selected.', 'error')
        return redirect(url_for('settings'))
    
    # Create new user
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
    
    # Permission check
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
    
    # Check if username is taken by another user
    existing_user = User.query.filter_by(username=username).first()
    if existing_user and existing_user.id != user.id:
        flash('Username already exists. Please choose a different one.', 'error')
        return redirect(url_for('settings'))
    
    # Check if email is taken by another user
    if email:
        existing_email = User.query.filter_by(email=email).first()
        if existing_email and existing_email.id != user.id:
            flash('Email address is already in use.', 'error')
            return redirect(url_for('settings'))
    
    # Update user info
    user.username = username
    user.email = email
    user.branch = branch
    
    # Only master admin can change roles
    if current_user.is_master_admin() and role:
        user.role = role
    
    db.session.commit()
    flash(f'User "{username}" updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/change_password/<int:user_id>', methods=['POST'])
@login_required
def change_password(user_id):
    user = User.query.get_or_404(user_id)
    
    # Permission check
    if not current_user.is_master_admin() and current_user.id != user_id:
        flash('You can only change your own password.', 'error')
        return redirect(url_for('settings'))
    
    current_password = request.form.get('current_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    # For non-master admin, verify current password
    if current_user.id == user_id and not current_user.is_master_admin():
        if not current_password or not check_password_hash(user.password, current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('settings'))
    
    # Validate new password
    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'error')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('settings'))
    
    # Update password
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
    
    # Prevent master admin from deactivating themselves
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
    
    # Prevent master admin from deleting themselves
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
    
    # Check if service is being used by any customers
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
    
    # Check if barber has active customers
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

# ============================================================================
# UTILITY FUNCTIONS FOR MAINTENANCE
# ============================================================================

def migrate_database():
    """Handle database schema migrations"""
    try:
        # Check if email column exists in user table
        with db.engine.connect() as conn:
            result = conn.execute(db.text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result.fetchall()]
            
            # Add email column if it doesn't exist
            if 'email' not in columns:
                print("Adding email column to user table...")
                conn.execute(db.text("ALTER TABLE user ADD COLUMN email VARCHAR(120) UNIQUE"))
                conn.commit()
                print("✅ Email column added successfully!")
            
            # Check if password_reset table exists
            result = conn.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='password_reset'"))
            if not result.fetchone():
                print("Creating password_reset table...")
                # Let SQLAlchemy create the table
                PasswordReset.__table__.create(db.engine, checkfirst=True)
                print("✅ Password reset table created successfully!")
                
    except Exception as e:
        print(f"Migration error: {e}")
        print("⚠️  You may need to delete the database file and restart")

def cleanup_expired_resets():
    """Remove expired password reset tokens"""
    expired = PasswordReset.query.filter(
        PasswordReset.expires_at < datetime.utcnow()
    ).all()
    
    for reset in expired:
        db.session.delete(reset)
    
    db.session.commit()
    return len(expired)

# ============================================================================
# INITIALIZATION
# ============================================================================

def create_sample_data():
    """Create sample data"""
    # Create branches
    branches_data = [
        {'code': 'main', 'name': 'Main Branch', 'address': '123 Oxford Street, Osu', 'phone': '0302-123-456'},
        {'code': 'downtown', 'name': 'Downtown Branch', 'address': '45 Kwame Nkrumah Ave, Adabraka', 'phone': '0302-789-012'},
        {'code': 'uptown', 'name': 'East Legon Branch', 'address': '78 Liberation Road, East Legon', 'phone': '0302-345-678'}
    ]
    
    for branch_data in branches_data:
        if not Branch.query.filter_by(code=branch_data['code']).first():
            branch = Branch(**branch_data)
            db.session.add(branch)
    
    # Create services
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
    
    # Create barbers
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
    
    # Create users - check if they exist first (safer approach)
    users_data = [
        {'username': 'master_admin', 'password': 'master123', 'role': 'master_admin', 'branch': 'main', 'email': 'master@trimq.com'},
        {'username': 'main_admin', 'password': 'main123', 'role': 'branch_admin', 'branch': 'main', 'email': 'main@trimq.com'},
        {'username': 'downtown_admin', 'password': 'downtown123', 'role': 'branch_admin', 'branch': 'downtown', 'email': 'downtown@trimq.com'},
        {'username': 'uptown_admin', 'password': 'uptown123', 'role': 'branch_admin', 'branch': 'uptown', 'email': 'uptown@trimq.com'}
    ]
    
    for user_data in users_data:
        try:
            # Check if user exists by username
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
                # Update existing user with email if they don't have one
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
        # Create all tables first
        db.create_all()
        
        # Handle database migrations
        migrate_database()
        
        # Create sample data
        create_sample_data()
        
        # Clean up any expired password reset tokens
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
        print("\n📧 Email Setup:")
        print("📌 Configure MAIL_USERNAME and MAIL_PASSWORD in app.py for password reset emails")
        print("📌 All demo accounts have email addresses set up for testing")
        print("\n🌐 Access: http://127.0.0.1:5000")
    
    app.run(debug=True)