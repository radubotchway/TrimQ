from datetime import datetime, timedelta
from app.models import Customer, Service

def get_wait_time(customer):
    """Calculate estimated wait time for a customer"""
    if customer.status != 'waiting':
        return None
    
    # Get all customers before this one in the queue
    earlier_customers = Customer.query.filter(
        Customer.branch == customer.branch,
        Customer.status == 'waiting',
        Customer.created_at < customer.created_at
    ).order_by(Customer.created_at).all()
    
    total_wait = 0
    for c in earlier_customers:
        service = Service.query.get(c.service_id)
        if service and service.duration:
            total_wait += service.duration
    
    if total_wait == 0:
        return "Now"
    
    wait_time = datetime.utcnow() + timedelta(minutes=total_wait)
    return wait_time.strftime('%H:%M')