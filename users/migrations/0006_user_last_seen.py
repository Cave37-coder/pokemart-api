# Hand-written (sandbox can't run Django's own makemigrations here -- see
# CLAUDE.md / project convention). Adds User.last_seen -- see the field's
# own help_text / the comment above it in models.py, and
# users/middleware.py, for why this exists and how it's kept up to date.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_user_update_emails_opt_out'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='last_seen',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Last time this customer was active on the site while logged in (updated automatically, not editable here).',
            ),
        ),
    ]
