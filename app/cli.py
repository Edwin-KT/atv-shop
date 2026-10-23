import click

from app.seed import seed_products
from app.services.users import create_admin


def register_commands(app):
    @app.cli.command("seed-products")
    def seed_products_command():
        """Insert sample products into the database."""
        click.echo(f"Added {seed_products()} product(s).")

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.argument("phone")
    @click.password_option()
    def create_admin_command(email, phone, password):
        """Create an admin user. The password is asked interactively."""
        try:
            admin = create_admin(email, phone, password)
        except ValueError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Admin created: {admin.email}")