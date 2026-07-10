import reflex as rx

from griffin_reflex.data_layer import save_research_goal


class OnboardingState(rx.State):
    research_goal: str = ""

    @rx.event
    def set_research_goal(self, value: str):
        self.research_goal = value

    @rx.event
    def start(self):
        goal = (self.research_goal or "").strip()
        if goal:
            save_research_goal(goal)
        # Land on planner; user can paste/edit goal there (State.query is separate)
        return rx.redirect("/")


def onboarding():
    return rx.center(
        rx.vstack(
            rx.heading("🧬 Welcome to Griffin AI", size="9"),
            rx.text("Your autonomous scientific research partner"),
            rx.input(
                placeholder="What do you want to research?",
                value=OnboardingState.research_goal,
                on_change=OnboardingState.set_research_goal,
                width="100%",
                size="3",
            ),
            rx.text(
                "Your goal is saved to dataset/last_research_goal.txt and shown on the Dashboard. "
                "Use the Planner to run the full multi-agent pipeline.",
                size="2",
                color="gray",
            ),
            rx.button(
                "Start AI Scientist",
                on_click=OnboardingState.start,
                color_scheme="indigo",
                size="3",
            ),
            rx.link("Skip to Dashboard", href="/dashboard", color="gray"),
            spacing="6",
            width="100%",
            max_width="520px",
            padding="40px",
        ),
        height="100vh",
        style={
            "background": "radial-gradient(ellipse at top, #111827, #020617)",
        },
    )
