import click

from app.seed import seed_products


def register_commands(app):
    @app.cli.command("seed-products")
    def seed_products_command():
        """Insert sample products into the database."""
        click.echo(f"Added {seed_products()} product(s).")