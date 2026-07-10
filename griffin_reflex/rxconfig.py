import reflex as rx
import os

config = rx.Config(
    app_name="griffin_reflex",
    api_url=os.environ.get("API_URL", "http://localhost:8000"),
    cors_allowed_origins=["*"],
    # Allow all subdomains on localtunnel for remote testing
    # Note: Vite uses this to prevent DNS rebinding attacks
    vite_allowed_hosts=[".loca.lt", "localhost", "127.0.0.1"],
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="dark",
                has_background=True,
                radius="large",
                scaling="100%",
                accent_color="indigo",
                gray_color="slate",
                panel_background="translucent",
            )
        ),
    ],
)
