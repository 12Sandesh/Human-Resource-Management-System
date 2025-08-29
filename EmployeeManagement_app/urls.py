from django.urls import path
from EmployeeManagement_app import views

urlpatterns = [
    path('<str:employee_id>/dashboard/', views.employee_dashboard, name='employee-dashboard'),

    path('<str:employee_id>/attendance/export/', views.export_attendance_report, name='export-attendance'),
    path('<str:employee_id>/attendance/', views.attendance, name='employee-attendance'),

    path('<str:employee_id>/leave/', views.leave, name='employee-leave'),

    path('<str:employee_id>/payroll/', views.payroll, name='employee-payroll'),
]

