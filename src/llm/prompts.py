"""
Prompt templates for LLM interactions.
Centralizes all prompt strings for better maintainability.
"""

from string import Template


class PromptTemplates:
    """Collection of prompt templates for various LLM interactions."""

    # Character/Player prompts
    CHARACTER_DESCRIPTION = Template(
        """Provide a ${word_count}-word brief description of your character named ${name}."""
    )

    CHARACTER_SELF_DESCRIPTION = Template(
        """These are details about yourself.
Name: ${name}
Description: ${description}"""
    )

    # Room description prompts
    ROOM_DESCRIPTION = Template(
        """Provide a ${word_count}-word description for the room that has just been created and the paths leading out of it:
room_name: ${room_name}
room_paths: ${room_paths}

If the path has a room_id, it means there is already a room there.
If the path has 'unknown', it means the path is open to be explored."""
    )

    ROOM_CONNECTION_UPDATE = Template(
        """The room ${room_name} has just been connected to a new room ${connected_room_name} via the ${direction} path.
Only update the room's path description to reflect this new connection.

Current description: ${current_description}

Provide the new description."""
    )

    ROOM_INTERACTION_UPDATE = Template(
        """The player has just performed the following interaction in the room:

${interaction}

---
Update the description of the room to reflect this interaction. Do not mention the player or the event specifically.

Current room description: ${current_description}"""
    )

    # Memory synthesis prompts
    UPDATE_PLAYER_MEMORY = Template(
        """Update your mental description of ${player_name} based on your most recent interaction with them.

Current Description: 
${current_description}

---
Recent Interaction: 
${interaction_content}

Provide only the updated description, no preamble."""
    )

    UPDATE_ROOM_MEMORY = Template(
        """Update your mental description of ${room_id} based on your most recent observations.

Current Description:
${current_description}

---
Recent Observation:
${observation}

Provide only the updated description, no preamble."""
    )

    # Action prompts
    NPC_ACTION_PROMPT = Template(
        """As an NPC named ${npc_name}, you have decided to <${action_name}>: ${action_description}.
${player_prompt}

Provide a brief response describing what you do."""
    )

    # System prompts
    PLAYER_SYSTEM_PROMPT = """You are an adventurer in a text-based exploration game. Make decisions based on your surroundings and history."""

    DM_SYSTEM_PROMPT = """You are the Dungeon Master overseeing a text-based exploration game. There are multiple players exploring a world made up of interconnected rooms. Your task is to generate descriptions for newly created rooms based on their connections and paths. Do not mention anything about the players themselves."""

    # World generation prompts (used by WorldGenerator)
    WORLD_GEN_ROOM_DESCRIPTION = Template(
        """Provide a ${word_count}-word description for the room that has just been created and the paths leading out of it:
room_name: ${room_name}
room_paths: ${room_paths}

If the path has a room_id, it means there is already a room there.
If the path has `unknown`, it means the path is open to be explored.
"""
    )

    WORLD_GEN_ROOM_CONNECTION = Template(
        """The room ${room_name} has just been connected to a new room ${new_room_name} via the ${direction} path.
Only update the room's path description to reflect this new connection. Current description: ${current_description}.
Provide the new description.
"""
    )


class PromptBuilder:
    """Helper class for building complex prompts."""

    @staticmethod
    def build_character_prompt(name: str, word_count: int = 20) -> str:
        """Build a character description prompt."""
        return PromptTemplates.CHARACTER_DESCRIPTION.substitute(
            name=name, word_count=word_count
        )

    @staticmethod
    def build_room_description_prompt(
        room_name: str, room_paths: dict, word_count: int = 100
    ) -> str:
        """Build a room description prompt."""
        path_descriptions = {
            d: desc if desc is not None else "unknown" for d, desc in room_paths.items()
        }
        return PromptTemplates.ROOM_DESCRIPTION.substitute(
            room_name=room_name, room_paths=path_descriptions, word_count=word_count
        )

    @staticmethod
    def build_memory_update_prompt(
        player_name: str, current_description: str, interaction_content: str
    ) -> str:
        """Build a player memory update prompt."""
        return PromptTemplates.UPDATE_PLAYER_MEMORY.substitute(
            player_name=player_name,
            current_description=(
                current_description if current_description else "No prior description."
            ),
            interaction_content=(
                interaction_content
                if interaction_content
                else "No recent interactions."
            ),
        )

    @staticmethod
    def build_room_memory_update_prompt(
        room_id: str, current_description: str, observation: str
    ) -> str:
        """Build a room memory update prompt."""
        return PromptTemplates.UPDATE_ROOM_MEMORY.substitute(
            room_id=room_id,
            current_description=(
                current_description if current_description else "No prior description."
            ),
            observation=observation,
        )
