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
6. Render a first-person perspective within this location/area/space (can be indoor room, outdoor clearing, tunnel, etc.)

INPUT TO CONVERT:
Art Style: ${art_style}
Location Name: ${room_name}
Location Description: ${room_description}
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

    # Decision prompt: Does this interaction visually modify the room?
    INTERACTION_VISUAL_IMPACT = Template(
        """Does this player action visually/physically change the room's appearance?

PLAYER ACTION: ${interaction}
CURRENT ROOM: ${room_description}

VISUAL CHANGE means:
- Physical alteration (opening doors, lighting fires, breaking objects, moving furniture)
- Adding/removing visible elements
- Changing lighting or atmosphere significantly

NOT VISUAL CHANGE:
- Reading, examining, looking at something
- Listening, smelling, touching without effect
- Talking, thinking, remembering
- Minor interactions that don't alter the scene

Respond with ONLY one word: YES or NO"""
    )

    # Minimal description update for visual changes (keep scene consistent)
    ROOM_VISUAL_UPDATE = Template(
        """The player performed this action: ${interaction}

CRITICAL: Make a MINIMAL update to the room description to reflect ONLY what changed.
Keep 90% of the original description intact - just modify the specific element affected.

Original description:
${current_description}

Updated description (keep it nearly identical, just reflect the change):"""
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
        """Generate a short, evocative name for this D&D location.

${adjacent_rooms}

CRITICAL: Your response must be ONLY the location name. No explanations, no parentheses, no additional text.

LOCATION TYPES (be varied, not just indoor rooms):
- Indoor: chambers, halls, vaults, corridors, cellars, throne rooms
- Outdoor: clearings, groves, cliffs, ruins, bridges, camps
- Transitional: archways, passages, thresholds, cave mouths, stairways
- Natural: pools, grottos, chasms, ledges, nests

Requirements:
- 2-4 words maximum
- Be creative and unique
- Evocative and atmospheric
- Can relate to adjacent areas OR be completely different
- NOT a huge region (keep it a single explorable area/space)

Your location name (2-4 words):"""
    )

    WORLD_GEN_ROOM_DESCRIPTION = Template(
        """Describe this ${word_count}-word location for a D&D game:
Location: ${room_name}
Exits: ${room_paths}

${adjacent_rooms}

CRITICAL: Your response must be ONLY the pure description text. DO NOT include the location name.

IMPORTANT: Create a location (room, area, clearing, passage, etc.) with DRAMATIC progression:
- NOT limited to indoor rooms - can be outdoor spaces, natural formations, transitional areas
- Keep it a single explorable AREA (not a vast region or entire forest)
- If adjacent locations describe a biome, STAY in that biome BUT show DRAMATIC changes within it
- Each location should feel like a SIGNIFICANT step deeper/forward, not just "more of the same"
- Include sensory details (see/hear/smell/feel) that INTENSIFY or SHIFT
- ONE memorable feature that's DIFFERENT from adjacent locations
- Show evolution, escalation, or transformation within the biome

Your description (${word_count} words max, NO location name):"""
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

CRITICAL: 1 OR 2 SHORT SENTENCE ONLY. Emphasize recognition, change, and that the player has entered the room. Second person ("You"). Avoid similar phrasing as recent narrations.



Your narration (1 or 2 short sentences):"""
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

    VOICEOVER_ROOM_CHANGE_NARRATION = Template(
        """Narrate how the room changed after the player's action.

Action: ${action_description}

BEFORE: ${before_description}

AFTER: ${after_description}

Recent narrations (don't repeat): ${recent_narrations}

CRITICAL: ONE SHORT SENTENCE ONLY. Describe the CHANGE - what shifted, opened, appeared, or transformed. Second person ("You see/hear/feel").

Examples:
- "Stone grinds against stone as a hidden passage opens."
- "The flames flicker and die, revealing ancient symbols beneath."
- "Crystal shards fall from the ceiling, tinkling like bells."

Your narration (one short sentence, focus on the CHANGE):"""
    )

    # Themed treasure name generation
    TREASURE_NAME_THEMED = Template(
        """Generate a treasure name that fits BOTH the room and world theme.

WORLD THEME: ${world_theme}
ROOM NAME: ${room_name}
ROOM DESCRIPTION: ${room_description}

The treasure should feel like it BELONGS in this specific room.
NOT generic mystical objects - something specific to this location.

Examples:
- Observatory + Space Station → "Captain's Navigation Crystal"
- Library + Haunted Manor → "Grimoire of the Fallen Lord"
- Kitchen + Pirate Ship → "Chef's Golden Ladle"
- Garden + Fairy Tale → "Enchanted Rose Seed"
- Throne Room + Medieval Castle → "Crown of the Last King"
- Laboratory + Sci-Fi → "Prototype Energy Core"

CRITICAL: Return ONLY the treasure name (2-5 words). No quotes, no explanation.

Treasure name:"""
    )

    # Description enhancement for treasure rooms
    ENHANCE_DESCRIPTION_FOR_TREASURE = Template(
        """Rewrite this room description to subtly emphasize one specific object that could hide a treasure.

ORIGINAL DESCRIPTION:
${original_description}

TREASURE TO HIDE: ${treasure_name}

INSTRUCTIONS:
1. Keep 80% of the original description intact
2. Add OR emphasize ONE object that could logically contain/hide the treasure
3. Make that object STAND OUT through vivid, curious description
4. Do NOT mention "treasure" or make it obvious
5. The object should feel naturally part of the scene but NOTABLE
6. At the END, add the hiding object in brackets like: [chest]

HIDING OBJECT TYPES (choose one that fits):
- Containers: chest, box, urn, cabinet, drawer, pouch, satchel
- Surfaces: pedestal, altar, table, shelf, throne, desk
- Hidden spots: loose brick, hollow tree, false floor, secret compartment
- Natural: rock, pool, roots, crystal, nest, shell

GOOD EXAMPLE:
BEFORE: "Dusty shelves line the walls. A faded tapestry hangs in the corner."
AFTER: "Dusty shelves line the walls. A faded tapestry hangs in the corner. Beneath the far window, an ornate wooden chest sits half-open, its brass hinges gleaming despite years of neglect. [chest]"

The player should read this and think "that object sounds interesting!"

Rewrite (end with [object_name]):"""
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
