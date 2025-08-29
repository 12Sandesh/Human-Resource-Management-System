from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from .models import Employee, Attendance, Leave, Payroll
from datetime import datetime, timedelta
import calendar
import csv
from django.http import HttpResponse


def employee_dashboard(request, employee_id):
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own dashboard
        if request.user.is_authenticated and hasattr(request.user, 'employee'):
            if request.user.employee.employee_id != employee_id:
                messages.error(request, 'Access denied.')
                return redirect('authapp-login')
        else:
            messages.error(request, 'Please log in.')
            return redirect('authapp-login')
            
        return render(request, 'EmployeeManagement_app/dashboard.html', {'employee': employee})
    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found.')
        return redirect('authapp-login')


def get_attendance_data(employee, period='current'):
    """Helper function to get attendance data for different periods"""
    today = timezone.now().date()
    
    if period == 'current':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'last':
        # Get last month's first and last day
        if today.month == 1:
            last_month = 12
            year = today.year - 1
        else:
            last_month = today.month - 1
            year = today.year
        
        start_date = datetime(year, last_month, 1).date()
        end_date = datetime(year, last_month, calendar.monthrange(year, last_month)[1]).date()
    else:  # all time - FIXED
        # Get the earliest attendance record or employee join date
        earliest_attendance = Attendance.objects.filter(employee=employee).order_by('date').first()
        if earliest_attendance:
            start_date = earliest_attendance.date
        else:
            # Fallback to employee join date or 1 year ago
            if hasattr(employee, 'date_joined') and employee.date_joined:
                start_date = employee.date_joined
            else:
                start_date = today - timedelta(days=365)
        end_date = today
    
    # Get attendance records for the period
    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__range=[start_date, end_date]
    ).order_by('-date')
    
    # Calculate statistics
    present_count = attendance_records.filter(status='Present').count()
    absent_count = attendance_records.filter(status='Absent').count()
    leave_count = attendance_records.filter(status='Leave').count()
    
    # Calculate total working days (excluding weekends)
    total_days = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            total_days += 1
        current_date += timedelta(days=1)
    
    # Calculate attendance rate
    if total_days > 0:
        attendance_rate = round((present_count / total_days) * 100, 1)
    else:
        attendance_rate = 0
    
    return {
        'attendance_records': attendance_records,
        'present_count': present_count,
        'absent_count': absent_count,
        'leave_count': leave_count,
        'total_working_days': total_days,
        'attendance_rate': attendance_rate,
        'period_label': get_period_label(period, start_date, end_date)
    }


def get_period_label(period, start_date, end_date):
    """Get human readable period label"""
    if period == 'current':
        return f"This Month ({start_date.strftime('%B %Y')})"
    elif period == 'last':
        return f"Last Month ({start_date.strftime('%B %Y')})"
    else:
        return f"All Time ({start_date.strftime('%b %Y')} - {end_date.strftime('%b %Y')})"


def attendance(request, employee_id):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Handle AJAX requests for period changes
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        period = request.GET.get('period', 'current')
        data = get_attendance_data(employee, period)
        
        # Convert attendance records to JSON serializable format
        records_data = []
        for record in data['attendance_records']:
            # Get the actual time when attendance was marked
            display_time = '--'
            if record.status == 'Present' and hasattr(record, 'marked_time') and record.marked_time:
                display_time = record.marked_time.strftime('%I:%M %p')
            elif record.status == 'Present':
                display_time = '09:00 AM'  # Default fallback
                
            records_data.append({
                'date': record.date.strftime('%Y-%m-%d'),
                'date_formatted': record.date.strftime('%b %d, %Y'),
                'day': record.date.strftime('%A'),
                'status': record.status,
                'time': display_time
            })
        
        return JsonResponse({
            'records': records_data,
            'present_count': data['present_count'],
            'absent_count': data['absent_count'],
            'leave_count': data['leave_count'],
            'total_working_days': data['total_working_days'],
            'attendance_rate': data['attendance_rate'],
            'period_label': data['period_label']
        })
    
    # Handle attendance marking
    if request.method == 'POST':
        today = timezone.now().date()
        current_time = timezone.now().time()
        
        # Check if attendance already marked today
        existing_attendance = Attendance.objects.filter(
            employee=employee,
            date=today
        ).first()
        
        if existing_attendance:
            messages.warning(request, "Attendance already marked for today.")
        else:
            # Mark attendance with current time
            attendance_record = Attendance.objects.create(
                employee=employee,
                date=today,
                status='Present'
            )
            # Store the actual time when attendance was marked
            attendance_record.marked_time = current_time
            attendance_record.save()
            
            messages.success(request, "Attendance marked successfully!")
            return redirect('employee-attendance', employee_id=employee_id)  # FIXED URL NAME
    
    # Get current month data by default
    attendance_data = get_attendance_data(employee, 'current')
    
    # Check if attendance marked today
    today = timezone.now().date()
    attendance_marked_today = Attendance.objects.filter(
        employee=employee,
        date=today
    ).exists()
    
    context = {
        'employee': employee,
        'attendance_records': attendance_data['attendance_records'],
        'present_count': attendance_data['present_count'],
        'absent_count': attendance_data['absent_count'],
        'leave_count': attendance_data['leave_count'],
        'total_working_days': attendance_data['total_working_days'],
        'attendance_rate': attendance_data['attendance_rate'],
        'attendance_marked_today': attendance_marked_today,
        'period_label': attendance_data['period_label']
    }
    
    return render(request, 'EmployeeManagement_app/attendance.html', context)


def leave(request, employee_id):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Handle leave application
    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        
        if leave_type and start_date and end_date and reason:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                if start_date <= end_date:
                    # Create leave record
                    leave_record = Leave.objects.create(
                        employee=employee,
                        leave_type=leave_type,
                        start_date=start_date,
                        end_date=end_date,
                        reason=reason
                    )
                    
                    # Auto-approve the leave and create attendance records
                    leave_record.status = 'Approved'
                    leave_record.save()
                    
                    # Create attendance records for leave days
                    current_date = start_date
                    while current_date <= end_date:
                        if current_date.weekday() < 5:  # Only weekdays
                            Attendance.objects.get_or_create(
                                employee=employee,
                                date=current_date,
                                defaults={'status': 'Leave'}
                            )
                        current_date += timedelta(days=1)
                    
                    messages.success(request, "Leave application submitted and approved successfully!")
                else:
                    messages.error(request, "End date must be after start date.")
            except ValueError:
                messages.error(request, "Invalid date format.")
        else:
            messages.error(request, "All fields are required.")
    
    # Get leave records and calculate duration for each
    leave_records = Leave.objects.filter(
        employee=employee
    ).order_by('-applied_at')
    
    # Add duration calculation to each leave record
    for leave in leave_records:
        leave.duration = (leave.end_date - leave.start_date).days + 1
    
    # Calculate leave statistics
    total_leaves = 20  # Assuming 20 total leaves per year
    used_leaves = leave_records.filter(status='Approved').count()
    remaining_leaves = total_leaves - used_leaves
    
    context = {
        'employee': employee,
        'leave_records': leave_records,
        'total_leaves': total_leaves,
        'used_leaves': used_leaves,
        'remaining_leaves': remaining_leaves,
    }
    
    return render(request, 'EmployeeManagement_app/leave.html', context)


def payroll(request, employee_id):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Get payroll records
    payroll_records = Payroll.objects.filter(
        employee=employee
    ).order_by('-payment_date')
    
    context = {
        'employee': employee,
        'payroll_records': payroll_records,
    }
    
    return render(request, 'EmployeeManagement_app/payroll.html', context)




def export_attendance_report(request, employee_id):
    """Export attendance report as CSV"""
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Get the period from request (default to current month)
    period = request.GET.get('period', 'current')
    attendance_data = get_attendance_data(employee, period)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    
    # Generate filename with period info
    period_label = attendance_data['period_label'].replace(' ', '_').replace('(', '').replace(')', '')
    filename = f"Attendance_Report_{employee.employee_id}_{period_label}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Employee ID',
        'Employee Name',
        'Date',
        'Day',
        'Status',
        'Time Marked',
        'Report Period',
        'Generated On'
    ])
    
    # Write attendance records
    for record in attendance_data['attendance_records']:
        time_marked = '--'
        if record.status == 'Present' and hasattr(record, 'marked_time') and record.marked_time:
            time_marked = record.marked_time.strftime('%I:%M %p')
        elif record.status == 'Present':
            time_marked = '09:00 AM'
            
        writer.writerow([
            employee.employee_id,
            employee.full_name,
            record.date.strftime('%Y-%m-%d'),
            record.date.strftime('%A'),
            record.status,
            time_marked,
            attendance_data['period_label'],
            timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Write summary statistics
    writer.writerow([])  # Empty row
    writer.writerow(['SUMMARY STATISTICS'])
    writer.writerow(['Present Days', attendance_data['present_count']])
    writer.writerow(['Absent Days', attendance_data['absent_count']])
    writer.writerow(['Leave Days', attendance_data['leave_count']])
    writer.writerow(['Total Working Days', attendance_data['total_working_days']])
    writer.writerow(['Attendance Rate', f"{attendance_data['attendance_rate']}%"])
    
    return response