import reflex as rx

config = rx.Config(
    app_name="griffin_reflex",
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
