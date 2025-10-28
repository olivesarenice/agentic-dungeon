# helpers
def checked_input(prompt: str) -> str:
    input_str = input(prompt + ": ")
    while input_str == "":
        print("No input found, please try again.")
        input_str = input(prompt)

    if input_str == "/q":
        print("Goodbye!")
        exit()
    else:
        return input_str


def prompt_user_choice(options: list[str]) -> str:
    print("Available options:")
    for option in options:
        print(f"- {option}")
    i = checked_input("What do you want to do next?").upper()

    while i not in options:
        print("Invalid move")
        i = checked_input("What do you want to do next?").upper()
    return i


def prompt_user_text(prompt: str) -> str:
    text = checked_input(prompt)
    return text
