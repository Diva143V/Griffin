class UserMemory:
    def __init__(self):
        self.memory = {}

    def remember(self, user, key, value):
        if user not in self.memory:
            self.memory[user] = {}
        self.memory[user][key] = value

    def recall(self, user):
        return self.memory.get(user, {})
