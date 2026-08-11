import re
from pathlib import Path


def extract_csrf_token(response):
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        response.get_data(as_text=True)
    )
    assert match is not None
    return match.group(1)


def test_post_without_csrf_token_is_rejected(client, app):
    app.config['WTF_CSRF_ENABLED'] = True

    response = client.post(
        '/auth/login',
        data={'email': 'user@example.com', 'password': 'Password123'}
    )

    assert response.status_code == 400
    assert 'İşlem doğrulanamadı' in response.get_data(as_text=True)


def test_post_with_valid_csrf_token_is_accepted(
    client,
    app,
    user_factory
):
    app.config['WTF_CSRF_ENABLED'] = True
    user_factory(
        email='csrf@example.com',
        password='Password123'
    )
    login_page = client.get('/auth/login')
    token = extract_csrf_token(login_page)

    response = client.post(
        '/auth/login',
        data={
            'email': 'csrf@example.com',
            'password': 'Password123',
            'csrf_token': token
        }
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')


def test_every_post_form_contains_csrf_token(app):
    template_root = Path(app.root_path) / 'templates'
    post_form_count = 0

    for template_path in template_root.rglob('*.html'):
        content = template_path.read_text(encoding='utf-8')
        form_count = len(
            re.findall(
                r'<form\b[^>]*\bmethod\s*=\s*["\']POST["\']',
                content,
                flags=re.IGNORECASE | re.DOTALL
            )
        )
        if not form_count:
            continue

        token_count = content.count('csrf_token()')
        assert token_count == form_count, (
            f'{template_path.name}: {form_count} POST formu var, '
            f'{token_count} CSRF tokenı bulundu.'
        )
        post_form_count += form_count

    assert post_form_count == 24
