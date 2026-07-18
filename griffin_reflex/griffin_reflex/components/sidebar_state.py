import reflex as rx

class SidebarState(rx.State):
    is_collapsed: bool = False

    @rx.event
    def toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
