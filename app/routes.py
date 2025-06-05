from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime
from app import db
from app.models import Customer, Barber, Service, Branch, User
from app.forms import (CustomerForm, BarberForm, ServiceForm, 
                      BranchForm, LoginForm)
from app.utils import get_wait_time
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.manage_queue', branch=user.branch))
        flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/add_customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            phone=form.phone.data,
            service_id=form.service_id.data,
            branch=form.branch.data,
            notes=form.notes.data
        )
        db.session.add(customer)
        db.session.commit()
        flash('Customer added to queue!', 'success')
        return redirect(url_for('main.manage_queue', branch=form.branch.data))
    return render_template('add_customer.html', form=form)

@bp.route('/manage/<branch>')
@login_required
def manage_queue(branch):
    if current_user.branch != branch and not current_user.is_admin:
        flash('You can only manage your own branch queue', 'danger')
        return redirect(url_for('main.manage_queue', branch=current_user.branch))
    
    waiting = Customer.query.filter_by(
        branch=branch, 
        status='waiting'
    ).order_by(Customer.created_at).all()
    
    in_progress = Customer.query.filter_by(
        branch=branch, 
        status='assigned'
    ).order_by(Customer.assigned_at).all()
    
    barbers = Barber.query.filter_by(
        branch=branch,
        is_active=True
    ).order_by(Barber.name).all()
    
    return render_template('manage.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         barbers=barbers,
                         branch=branch,
                         get_wait_time=get_wait_time)

@bp.route('/assign/<int:customer_id>', methods=['POST'])
@login_required
def assign_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if current_user.branch != customer.branch and not current_user.is_admin:
        flash('You can only manage your own branch queue', 'danger')
        return redirect(url_for('main.manage_queue', branch=current_user.branch))
    
    barber_id = request.form.get('barber_id')
    if barber_id:
        customer.barber_id = barber_id
        customer.status = 'assigned'
        customer.assigned_at = datetime.utcnow()
        db.session.commit()
        flash('Customer assigned to barber!', 'success')
    return redirect(url_for('main.manage_queue', branch=customer.branch))

@bp.route('/complete/<int:customer_id>')
@login_required
def complete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if current_user.branch != customer.branch and not current_user.is_admin:
        flash('You can only manage your own branch queue', 'danger')
        return redirect(url_for('main.manage_queue', branch=current_user.branch))
    
    customer.status = 'completed'
    customer.completed_at = datetime.utcnow()
    db.session.commit()
    flash('Service marked as completed!', 'success')
    return redirect(url_for('main.manage_queue', branch=customer.branch))

@bp.route('/queue/<branch>')
def public_queue(branch):
    waiting = Customer.query.filter_by(
        branch=branch, 
        status='waiting'
    ).order_by(Customer.created_at).all()
    
    in_progress = Customer.query.filter_by(
        branch=branch, 
        status='assigned'
    ).order_by(Customer.assigned_at).all()
    
    branch_info = Branch.query.filter_by(name=branch).first()
    
    return render_template('queue.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         branch=branch,
                         branch_info=branch_info,
                         get_wait_time=get_wait_time)

@bp.route('/barbers', methods=['GET', 'POST'])
@login_required
def manage_barbers():
    form = BarberForm()
    if form.validate_on_submit():
        barber = Barber(
            name=form.name.data,
            branch=form.branch.data
        )
        db.session.add(barber)
        db.session.commit()
        flash('Barber added successfully!', 'success')
        return redirect(url_for('main.manage_barbers'))
    
    barbers = Barber.query.order_by(Barber.branch, Barber.name).all()
    return render_template('barbers.html', form=form, barbers=barbers)

@bp.route('/services', methods=['GET', 'POST'])
@login_required
def manage_services():
    form = ServiceForm()
    if form.validate_on_submit():
        service = Service(
            name=form.name.data,
            duration=form.duration.data,
            price=form.price.data
        )
        db.session.add(service)
        db.session.commit()
        flash('Service added successfully!', 'success')
        return redirect(url_for('main.manage_services'))
    
    services = Service.query.order_by(Service.name).all()
    return render_template('services.html', form=form, services=services)

@bp.route('/branches', methods=['GET', 'POST'])
@login_required
def manage_branches():
    form = BranchForm()
    if form.validate_on_submit():
        branch = Branch(
            name=form.name.data,
            address=form.address.data,
            phone=form.phone.data
        )
        db.session.add(branch)
        db.session.commit()
        flash('Branch added successfully!', 'success')
        return redirect(url_for('main.manage_branches'))
    
    branches = Branch.query.order_by(Branch.name).all()
    return render_template('branches.html', form=form, branches=branches)

@bp.route('/toggle_barber/<int:barber_id>', methods=['POST'])
@login_required
def toggle_barber(barber_id):
    if not current_user.is_admin:
        flash('Only admin can manage barbers', 'danger')
        return redirect(url_for('main.index'))
    
    barber = Barber.query.get_or_404(barber_id)
    barber.is_active = not barber.is_active
    db.session.commit()
    flash(f'Barber {barber.name} has been {"activated" if barber.is_active else "deactivated"}', 'success')
    return redirect(url_for('main.manage_barbers'))

@bp.route('/toggle_service/<int:service_id>', methods=['POST'])
@login_required
def toggle_service(service_id):
    if not current_user.is_admin:
        flash('Only admin can manage services', 'danger')
        return redirect(url_for('main.index'))
    
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    flash(f'Service {service.name} has been {"activated" if service.is_active else "deactivated"}', 'success')
    return redirect(url_for('main.manage_services'))