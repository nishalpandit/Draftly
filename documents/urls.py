from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_explicit'),
    path('create/', views.create_document, name='create'),
    path('import/', views.import_document, name='import_document'),
    path('<int:pk>/', views.editor, name='editor'),
    path('<int:pk>/save/', views.save_document, name='autosave'),
    path('<int:pk>/delete/', views.delete_document, name='delete'),
    path('<int:pk>/share/', views.share_document, name='share'),
    path('<int:pk>/shares/<int:share_id>/update/', views.update_share, name='update_share'),
    path('<int:pk>/shares/<int:share_id>/revoke/', views.revoke_share, name='revoke_share'),
]
