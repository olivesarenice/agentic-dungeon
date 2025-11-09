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

    # Memory synthesis prompts - SPECIFIC STRUCTURED FORMAT
    UPDATE_PLAYER_MEMORY = Template(
        """Update your memory of ${player_name} based on this interaction:
${interaction_content}

Current memory:
${current_description}

FORMAT: Use EXACTLY this structure (bullet points only):
- My opinion of the player: [one brief phrase]
- Physical appearance: [one brief phrase]
- Personality: [one brief phrase]
- Any significant traits: [one brief phrase]
- Last seen in room: [room name or ID]

Good example:
- My opinion of the player: Trustworthy ally
- Physical appearance: Tall, wears blue robes
- Personality: Cautious but helpful
- Any significant traits: Skilled with magic
- Last seen in room: Dark Cavern

Bad example (TOO VERBOSE or WRONG FORMAT):
"This adventurer seems friendly and wears blue robes..."

Your updated memory (use exact format above):"""
    )

    UPDATE_ROOM_MEMORY = Template(
        """Update your memory of this location based on your observation:
${observation}

Current memory:
${current_description}

FORMAT: Use EXACTLY this structure (bullet points only):
- Physical appearance: [brief description]
- Other things notable to senses: [sounds, smells, temperature, etc.]
- Players present in the room with me: [list names, or "None" if alone]
- Players previously seen here: [list names of others seen before, or "None"]

Good example:
- Physical appearance: Dark stone chamber, damp walls
- Other things notable to senses: Water dripping, smells of earth, cold air
- Players present in the room with me: John, Sarah
- Players previously seen here: John, Sarah, Alex (no longer here)

Bad example (TOO VERBOSE or WRONG FORMAT):
"This is a dark chamber with water dripping..."

Your updated memory (use exact format above):"""
    )

    # Action prompts - CONCISE D&D style
    NPC_ACTION_PROMPT = Template(
        """You are ${npc_name} in ${room_name}.

Room: ${room_description}
Other players here: ${other_players}

Action: ${player_prompt}

IMPORTANT: Be concise like a D&D player. Use 1-2 short sentences maximum.
Consider the room and other players when responding.

Good examples:
- "I check the chest for traps"
- "I examine the ancient runes on the wall"
- "Hi everyone! Anyone need help?"

Bad examples (TOO VERBOSE):
- "Cautiously approaching the mysterious chest..."
- "With great care, I slowly move towards..."

Your response (1-2 sentences only):"""
    )

    # System prompts - EMPHASIZE CONCISENESS
    PLAYER_SYSTEM_PROMPT = """You are an adventurer in a text-based D&D game. 

IMPORTANT: Be concise. Respond like a D&D player would write on their character sheet.
- Use 1-2 short sentences for actions
- Use bullet points for observations
- No flowery language or lengthy descriptions

Think: "I check for traps" NOT "Cautiously, I approach the chest..."
"""

    DM_SYSTEM_PROMPT = """You are the Dungeon Master for a text-based D&D game.

IMPORTANT: Be concise and atmospheric:
- Room descriptions: 30-50 words max
- Focus on sensory details (see/hear/smell)
- Notable features only
- Set mood, don't tell stories

Think D&D session notes, not novel writing.
"""

    # World generation prompts (used by WorldGenerator) - CONCISE D&D style
    WORLD_GEN_ROOM_DESCRIPTION = Template(
        """Describe this ${word_count}-word room for a D&D game:
Room: ${room_name}
Exits: ${room_paths}

IMPORTANT: Be concise and atmospheric. Focus on:
1. What you see/hear/smell (sensory details)
2. Notable features
3. Mood/atmosphere

Good example (40 words):
"A damp stone chamber. Water drips from moss-covered walls. Ancient runes glow faintly blue, casting dancing shadows. The air smells of earth and old magic. Passages lead north and east into darkness."

Bad example (TOO VERBOSE/FLOWERY):
"As you enter this magnificent chamber, you are immediately struck by..."

Your description (${word_count} words max):"""
    )

    WORLD_GEN_ROOM_CONNECTION = Template(
        """Room ${room_name} now connects ${direction} to ${new_room_name}.

Current description:
${current_description}

Update briefly to mention the new ${direction} connection. Keep it concise (add 1 sentence max).

Updated description:"""
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
