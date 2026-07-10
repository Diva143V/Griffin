import reflex as rx

class OnboardingState(rx.State):
    research_goal: str = ""
    def start(self):
        return rx.redirect("/workspace")

def onboarding():
    return rx.center(
        rx.vstack(
            rx.heading(
                "🧬 Welcome to Griffin AI",
                size="9"
            ),
            rx.text(
                "Your autonomous scientific research partner"
            ),
            rx.input(
                placeholder="What do you want to research?",
                on_change=OnboardingState.set_research_goal
            ),
            rx.button(
                "Start AI Scientist",
                on_click=OnboardingState.start
            ),
            spacing="6"
        ),
        height="100vh"
    )
