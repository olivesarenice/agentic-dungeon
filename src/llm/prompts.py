"""
Prompt templates for LLM interactions.
Centralizes all prompt strings for better maintainability.
"""

from string import Template


class PromptTemplates:
    """Collection of prompt templates for various LLM interactions."""

    # Flash Image Model Prompt Optimization
    FLASH_IMAGE_OPTIMIZER = Template(
        """You are a prompt optimizer for image generation models. Your task is to convert a structured prompt into a "dense narrative" format optimized for Flash image models.

FLASH MODEL CHARACTERISTICS:
- Flash models are literal and work best with concrete visual descriptions
- They pay most attention to the first 20-30 words (front-load the style)
- They struggle with abstract concepts
- They cannot render non-visual elements (sounds, smells, feelings)
- They work best with a single continuous block of text (no headers or structure)

CONVERSION RULES:
1. Front-load the art style in the first sentence
2. Convert ALL abstract concepts to concrete visual descriptions:
   - "mystical energy" → "glowing blue particles floating, soft cyan rim lighting, magical aura distortion"
   - "ethereal shadows" → "long translucent shadows with soft purple and blue edges"
   - "ancient atmosphere" → "cracked weathered stone, moss-covered surfaces, dust motes in air"
3. Remove or convert non-visual elements
4. Add explicit texture and detail keywords:
   - Materials: "with visible grain texture", "sharp distinct reflections", "visible brushstrokes"
   - Lighting: "with visible rays", "with defined edges", "casting long sharp shadows"
5. Keep it as ONE continuous paragraph
6. Emphasize that it needs to render a perspective inside a physical ROOM.

INPUT TO CONVERT:
Art Style: ${art_style}
Room Name: ${room_name}
Room Description: ${room_description}
${player_info}

OUTPUT (dense narrative format, single paragraph, 100-150 words):"""
    )

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

Your response (1-2 sentences only):"""
    )

    # System prompts - EMPHASIZE CONCISENESS
    PLAYER_SYSTEM_PROMPT = """You are an adventurer in a text-based D&D game. 

IMPORTANT: Be concise. Respond like a D&D player would write on their character sheet.
- Use 1-2 short sentences for actions
- Use bullet points for observations
- No flowery language or lengthy descriptions

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
    WORLD_GEN_ROOM_NAME = Template(
        """Generate a short, evocative name for this D&D room/location.

${adjacent_rooms}

CRITICAL: Your response must be ONLY the room name. No explanations, no parentheses, no additional text.

Requirements:
- 2-4 words maximum
- Be creative and unique
- Evocative and atmospheric
- Can relate to adjacent rooms OR be completely different

Your room name (2-4 words):"""
    )

    WORLD_GEN_ROOM_DESCRIPTION = Template(
        """Describe this ${word_count}-word room for a D&D game:
Room: ${room_name}
Exits: ${room_paths}

${adjacent_rooms}

CRITICAL: Your response must be ONLY the pure description text. DO NOT include the room name.

IMPORTANT: Create a room with DRAMATIC progression and its own unique character.
- If adjacent rooms describe a biome, STAY in that biome BUT show DRAMATIC changes within it
- Each room should feel like a SIGNIFICANT step deeper/forward, not just "more of the same"
- Include sensory details (see/hear/smell/feel) that INTENSIFY or SHIFT
- ONE memorable feature that's DIFFERENT from adjacent rooms
- Show evolution, escalation, or transformation within the biome

Your description (${word_count} words max, NO room name):"""
    )

    WORLD_GEN_ROOM_CONNECTION = Template(
        """Room ${room_name} now connects ${direction} to ${new_room_name}.

Current description:
${current_description}

Update briefly to mention the new ${direction} connection. Keep it concise (add 1 sentence max).

Updated description:"""
    )

    # Voiceover narration prompts - PUNCHY AND IMMEDIATE
    VOICEOVER_MOVE_NARRATION = Template(
        """Narrate the player moving ${direction} to ${to_room_name}.

TO ROOM: ${to_room_description}
First visit: ${is_first_visit}

Recent narrations (don't repeat): ${recent_narrations}

STYLE RULES:
- If First visit = "Yes": 1-2 sentences describing what YOU DO and how YOU REACT to the new space
- If First visit = "No": ONE SHORT SENTENCE about returning

Examples for FIRST VISIT (describe player's actions):
- "You push through the archway and freeze - the walls pulse with an eerie blue glow that makes your skin tingle."
- "You step forward into darkness, and your breath catches as you hear water dripping somewhere far below."
- "You enter cautiously, eyes adjusting to the dim light as the smell of ancient dust fills your lungs."

Examples for RETURNING:
- "You return to the familiar chamber."
- "Back again."

Your narration (describe what the PLAYER does):"""
    )

    VOICEOVER_ACTION_NARRATION = Template(
        """Narrate this action: ${action_type} - ${action_content}

Room: ${room_description}
Others present: ${npcs_present}

Recent narrations (don't repeat): ${recent_narrations}

CRITICAL: ONE SHORT SENTENCE ONLY. Focus on immediate physical sensation or reaction. Second person ("You").

Examples:
- "Your words echo off stone walls."
- "Cold metal under your fingertips."
- "Something glints in the darkness ahead."

Your narration (one short sentence):"""
    )

    VOICEOVER_RETURN_NARRATION = Template(
        """Narrate returning to ${room_name}.

Room: ${room_description}

Recent narrations (don't repeat): ${recent_narrations}

CRITICAL: ONE SHORT SENTENCE ONLY. Emphasize recognition or change. Second person ("You").

Examples:
- "The musty air - instantly familiar."
- "Something's different here."
- "Back again, like you never left."

Your narration (one short sentence):"""
    )

    VOICEOVER_FIRST_VISIT_NARRATION = Template(
        """Narrate entering ${room_name} for the first time.

Room: ${room_description}

Recent narrations (don't repeat): ${recent_narrations}

CRITICAL: ONE SHORT SENTENCE ONLY. Lead with the most striking detail. Second person ("You").

Examples:
- "The walls pulse with bioluminescent light."
- "Water drips somewhere in the darkness below."
- "Ancient symbols cover every surface."

Your narration (one short sentence):"""
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
