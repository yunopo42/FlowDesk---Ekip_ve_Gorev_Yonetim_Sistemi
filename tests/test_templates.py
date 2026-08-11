def test_all_jinja_templates_compile(app):
    with app.app_context():
        template_names = app.jinja_env.list_templates()
        for template_name in template_names:
            app.jinja_env.get_template(template_name)

    assert 'errors/csrf.html' in template_names
