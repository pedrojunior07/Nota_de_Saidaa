from app import create_app

app = create_app()
with app.app_context():
    from app.services.seed import executar_seed
    executar_seed(forcar=True)
    from app.models.user import User
    users = [(u.username, u.perfil, u.verificar_password('Standard@2026')) for u in User.query.order_by(User.username).all()]
    print(users)
    client = app.test_client()
    resp = client.get('/login')
    print('status=', resp.status_code)
    html = resp.get_data(as_text=True)
    print('has_favicon=', 'logo_std_stacked%20-%20Cropped.png' in html)
