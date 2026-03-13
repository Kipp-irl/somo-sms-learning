"""
curriculum.py -- Kenya CBC (Competency-Based Curriculum) definitions for Somo.

Models the grade/class system after Kenya's CBC structure:

  Pre-Primary     : PP1, PP2
  Lower Primary   : Grade 1, Grade 2, Grade 3
  Upper Primary   : Grade 4, Grade 5, Grade 6
  Junior Secondary: Grade 7, Grade 8, Grade 9   (Junior School)
  Senior Secondary: Grade 10, Grade 11, Grade 12 (Senior School)

Each level has its own set of learning areas (subjects) aligned to the
CBC framework published by KICD (Kenya Institute of Curriculum Development).
"""

import re

# ── Grade levels available for registration ──────────────

CBC_LEVELS = [
    # (display_value, level_band)
    ("PP1", "Pre-Primary"),
    ("PP2", "Pre-Primary"),
    ("Grade 1", "Lower Primary"),
    ("Grade 2", "Lower Primary"),
    ("Grade 3", "Lower Primary"),
    ("Grade 4", "Upper Primary"),
    ("Grade 5", "Upper Primary"),
    ("Grade 6", "Upper Primary"),
    ("Grade 7", "Junior Secondary"),
    ("Grade 8", "Junior Secondary"),
    ("Grade 9", "Junior Secondary"),
    ("Grade 10", "Senior Secondary"),
    ("Grade 11", "Senior Secondary"),
    ("Grade 12", "Senior Secondary"),
]

# Quick lookup: grade string -> band
GRADE_TO_BAND = {grade: band for grade, band in CBC_LEVELS}


# ── CBC Curriculum by level band ─────────────────────────
# Subjects (learning areas) and expected competencies per band,
# aligned with KICD's CBC framework.

CURRICULUM: dict[str, dict[str, str]] = {

    # ── Pre-Primary (PP1-PP2) ────────────────────────────
    "Pre-Primary": {
        "Language Activities": (
            "Listening and speaking skills, pre-reading activities (picture reading, "
            "letter recognition), pre-writing (patterns, letter formation), "
            "name writing, nursery rhymes, storytelling and picture description"
        ),
        "Mathematical Activities": (
            "Number recognition 1-50, counting objects, sorting by size/colour/shape, "
            "simple patterns, comparing (more/less, big/small, tall/short), "
            "basic addition within 10 using objects, spatial awareness (in, on, under)"
        ),
        "Environmental Activities": (
            "My body and senses, personal hygiene and grooming, family members and roles, "
            "domestic and wild animals, plants around us, weather observation, "
            "clean and dirty environments, food groups and healthy eating"
        ),
        "Psychomotor & Creative Activities": (
            "Drawing and colouring, modelling with clay/plasticine, paper folding, "
            "singing and dancing, outdoor play (running, jumping, throwing, catching), "
            "balancing, basic rhythmic movements, simple musical instruments"
        ),
        "Religious Education": (
            "God as creator, simple prayers, good behaviour and moral values, "
            "respect for others, sharing and kindness, stories from holy books"
        ),
    },

    # ── Lower Primary (Grade 1-3) ────────────────────────
    "Lower Primary": {
        "English": (
            "Phonics and blending, reading CVC and CVCC words, sight words, "
            "simple sentences (3-7 words), capital letters and full stops, "
            "common nouns and verbs, simple past tense, paragraph reading, "
            "picture composition, days of the week, months of the year, "
            "short stories, conversation skills"
        ),
        "Kiswahili": (
            "Herufi za Kiswahili (silabi), kusoma maneno rahisi, "
            "kuandika sentensi fupi, majina ya watu na vitu, "
            "salamu za kila siku, nyimbo za watoto, hadithi fupi, "
            "utambuzi wa sauti, misamiati ya msingi"
        ),
        "Indigenous Language": (
            "Mother tongue activities: listening and responding, "
            "naming objects and people, simple greetings and conversations, "
            "oral stories and songs from the community, "
            "basic reading and writing in the local language"
        ),
        "Mathematics": (
            "Counting to 1000, place value (ones, tens, hundreds), "
            "addition and subtraction within 999, basic multiplication (tables 1-5), "
            "simple division, fractions (1/2, 1/4, 1/3), "
            "telling time (hours and half hours), measuring length (cm, m), "
            "Kenyan money (coins and notes), simple patterns and sequences, "
            "basic shapes (circle, square, triangle, rectangle)"
        ),
        "Environmental Activities": (
            "Living and non-living things, basic needs of plants and animals, "
            "parts of a plant, domestic and wild animals of Kenya, "
            "weather patterns, water sources and uses, soil types, "
            "personal hygiene, nutrition and food groups, "
            "home safety, the school environment"
        ),
        "Hygiene & Nutrition": (
            "Handwashing, dental care, bathing and grooming, "
            "clean water and safe food handling, balanced diet, "
            "common childhood diseases and prevention, first aid basics, "
            "exercise and rest, keeping the environment clean"
        ),
        "Religious Education": (
            "Creation stories, prayer and worship, the family unit, "
            "moral values (honesty, respect, kindness, obedience), "
            "Bible/Quran/Hindu stories, places of worship, "
            "festivals and celebrations"
        ),
        "Creative Arts": (
            "Drawing and painting, paper craft and collage, clay modelling, "
            "singing Kenyan children's songs, simple percussion instruments, "
            "action songs and dances, puppetry, colour mixing"
        ),
        "Physical & Health Education": (
            "Running, jumping, skipping, throwing and catching, "
            "simple ball games, relay races, balancing exercises, "
            "basic gymnastics, traditional Kenyan games, safety during play"
        ),
    },

    # ── Upper Primary (Grade 4-6) ────────────────────────
    "Upper Primary": {
        "English": (
            "Paragraph writing with topic sentences, parts of speech (nouns, verbs, "
            "adjectives, adverbs, prepositions), verb tenses (past, present, future), "
            "subject-verb agreement, reading comprehension passages, "
            "synonyms and antonyms, prefixes and suffixes, letter and diary writing, "
            "direct and indirect speech, punctuation (commas, apostrophes, quotation marks), "
            "simple poems and oral recitation"
        ),
        "Kiswahili": (
            "Ufahamu wa habari, aina za maneno (nomino, vitenzi, vivumishi), "
            "nyakati za vitenzi, uandishi wa insha na barua, "
            "methali na nahau, sarufi ya msingi, "
            "fasihi (hadithi fupi, mashairi), mazungumzo, usomaji wa vitabu"
        ),
        "Mathematics": (
            "Multiplication and division up to 4 digits, fractions (add, subtract, compare), "
            "decimals and place value, percentages introduction, area and perimeter of rectangles, "
            "angles (acute, right, obtuse), coordinate grids, order of operations (BODMAS), "
            "mean/average, factors and multiples, LCM and GCD, "
            "Kenyan currency calculations, simple data handling (bar graphs, pictographs)"
        ),
        "Science & Technology": (
            "States of matter (solid, liquid, gas) and changes, water cycle, "
            "simple machines (lever, pulley, inclined plane), food chains and webs, "
            "human body systems (digestive, respiratory, circulatory), "
            "the solar system, magnets and static electricity, "
            "rocks and soil types, photosynthesis, "
            "basic computing (parts of a computer, typing, internet safety)"
        ),
        "Social Studies": (
            "The map of Kenya (counties, major towns, physical features), "
            "Kenyan communities and cultures, government of Kenya (national and county), "
            "rights and responsibilities of citizens, "
            "history of Kenya (pre-colonial, colonial, independence), "
            "economic activities (farming, fishing, trade, tourism), "
            "transport and communication in Kenya, "
            "environmental conservation and management"
        ),
        "Agriculture": (
            "Types of farming in Kenya (crop and animal), soil and water conservation, "
            "planting and caring for crops, common crops in Kenya (maize, beans, tea, coffee), "
            "farm animals and their products, simple farm tools, "
            "pests and diseases, kitchen garden, agroforestry"
        ),
        "Home Science": (
            "Food preparation and preservation, nutrition and meal planning, "
            "kitchen hygiene and safety, needlework (stitching, knitting), "
            "laundry and clothing care, home management, "
            "child care basics, consumer awareness"
        ),
        "Religious Education": (
            "Moral values and character formation, stories of faith leaders, "
            "worship and community, the Ten Commandments / Five Pillars, "
            "parables and their meanings, caring for others, "
            "family and social responsibility"
        ),
        "Creative Arts": (
            "Drawing techniques (perspective, shading), painting and colour theory, "
            "weaving and beadwork (Kenyan crafts), music notation basics, "
            "Kenyan folk songs and dances, drama and role play, "
            "instrument playing (recorder, drum), art appreciation"
        ),
        "Physical & Health Education": (
            "Athletics (running, jumping, throwing), ball games (football, netball, volleyball), "
            "swimming basics, gymnastics, traditional Kenyan dances and games, "
            "sportsmanship, substance abuse awareness, first aid, "
            "adolescence and personal health"
        ),
    },

    # ── Junior Secondary (Grade 7-9) ─────────────────────
    "Junior Secondary": {
        "English": (
            "Essay writing (narrative, descriptive, persuasive, expository), "
            "figurative language (similes, metaphors, personification, alliteration), "
            "critical reading and inference, active and passive voice, "
            "reported speech, relative clauses, formal vs informal register, "
            "comprehension of poetry and prose, debate and argument structure, "
            "research skills, summary and note-making, public speaking"
        ),
        "Kiswahili": (
            "Uandishi wa insha za aina mbalimbali, fasihi simulizi na andishi, "
            "sarufi ya kina (ngeli, nyakati, kauli), uchanganuzi wa hadithi na mashairi, "
            "hotuba na midahalo, muhtasari, maswali ya ufahamu, "
            "isimu jamii, methali na misemo, taarifa na barua rasmi"
        ),
        "Mathematics": (
            "Algebraic expressions and simple equations, ratios and proportions, "
            "percentages (profit/loss, discount, simple interest), coordinate geometry, "
            "statistics (mean, median, mode, range, frequency tables), probability basics, "
            "Pythagorean theorem, transformations (reflection, rotation, translation), "
            "linear graphs, indices and powers, number patterns, "
            "geometry of circles, surface area and volume"
        ),
        "Integrated Science": (
            "Atomic structure basics, elements and compounds, chemical reactions (acids/bases), "
            "forces and motion (Newton's laws), energy types and conversion, "
            "electricity (circuits, voltage, current, resistance), cells and cell division, "
            "genetics basics (traits, inheritance), classification of organisms, "
            "Earth's layers and plate tectonics, the environment and ecology, "
            "health and disease, scientific investigation methods"
        ),
        "Social Studies": (
            "History of East Africa and Kenya (pre-colonial, colonial, independence), "
            "government systems (democracy, constitution, devolution in Kenya), "
            "human rights and responsibilities, economics (supply/demand, trade, currency), "
            "urbanization, migration and population, African Union and EAC, "
            "globalization, environmental challenges (climate change, deforestation), "
            "citizenship and national cohesion"
        ),
        "Pre-Technical & Pre-Career Education": (
            "Woodwork and metalwork basics, technical drawing, "
            "basic electronics, home electrical wiring safety, "
            "computer applications (word processing, spreadsheets, presentations), "
            "coding introduction (block-based programming), internet literacy, "
            "entrepreneurship basics, career awareness and guidance"
        ),
        "Agriculture": (
            "Soil science (types, pH, fertility), crop production processes, "
            "animal husbandry (dairy, poultry, beekeeping), farm planning and records, "
            "water management and irrigation, agricultural economics, "
            "pest and disease management, organic farming, food security in Kenya"
        ),
        "Creative Arts & Sports": (
            "Visual arts (painting, sculpture, graphic design basics), "
            "performing arts (music theory, dance, drama, theatre), "
            "Kenyan cultural heritage through arts, "
            "competitive sports (athletics, team sports, individual sports), "
            "fitness and wellness, sportsmanship and fair play"
        ),
        "Religious Education": (
            "Comparative religion, ethics and moral reasoning, "
            "religious leaders and reformers, social justice, "
            "contemporary moral issues, faith and science, "
            "community service, personal spiritual growth"
        ),
        "Health Education": (
            "Adolescent health and puberty, reproductive health basics, "
            "mental health awareness, nutrition and lifestyle diseases, "
            "substance abuse prevention, HIV/AIDS awareness, "
            "first aid and emergency response, water and sanitation"
        ),
        "Business Studies": (
            "Introduction to business, trade and commerce, "
            "simple bookkeeping and accounting, entrepreneurship, "
            "consumer rights, banking and financial literacy, "
            "marketing basics, office practice"
        ),
    },

    # ── Senior Secondary (Grade 10-12) ───────────────────
    # CBC Senior School uses pathways: STEM, Arts & Sports Science,
    # Social Sciences, Languages & Literature.
    # Core subjects are listed plus common pathway electives.

    "Senior Secondary": {
        "English": (
            "Literary analysis (character, theme, setting, style), "
            "academic and research writing, advanced grammar (conditionals, inversion), "
            "rhetoric and persuasion techniques, critical essay writing, "
            "comprehension of novels, plays, and poetry (set books), "
            "register and tone analysis, oral presentation and debate, "
            "summary and synthesis, creative writing techniques, media literacy"
        ),
        "Kiswahili": (
            "Fasihi ya Kiswahili (riwaya, tamthilia, ushairi, hadithi fupi), "
            "uchanganuzi wa kazi za fasihi, sarufi ya hali ya juu, "
            "utungaji wa insha za kitaaluma, uandishi wa habari, "
            "isimu na mofolojia, lugha ya biashara, tafsiri, "
            "fasihi simulizi ya jamii za Kenya"
        ),
        "Mathematics": (
            "Quadratic equations and formula, trigonometry (sin, cos, tan, identities), "
            "sequences and series (arithmetic, geometric), logarithms, "
            "vectors in 2D, matrices (operations, determinants), "
            "calculus introduction (differentiation and integration), "
            "probability distributions, set theory, surds and indices, "
            "simultaneous equations, circle theorems, "
            "statistics (standard deviation, regression)"
        ),
        "Biology": (
            "Cell biology (organelles, transport, division), "
            "genetics and heredity (DNA, Mendelian genetics, mutations), "
            "evolution and natural selection, ecology (biomes, nutrient cycles, food webs), "
            "human physiology (nervous, endocrine, reproductive systems), "
            "plant biology (photosynthesis, transport, reproduction), "
            "classification and biodiversity, biotechnology, "
            "health and diseases, experimental biology"
        ),
        "Chemistry": (
            "Atomic structure and periodic table, chemical bonding, "
            "stoichiometry and mole concept, organic chemistry (alkanes, alkenes, alcohols), "
            "acids, bases and salts, redox reactions, electrochemistry, "
            "rates of reaction and equilibrium, energy changes in reactions, "
            "industrial chemistry (Haber process, extraction of metals), "
            "environmental chemistry, analytical techniques"
        ),
        "Physics": (
            "Mechanics (forces, motion, Newton's laws, energy, momentum), "
            "waves (sound, light, electromagnetic spectrum), "
            "electricity and magnetism (circuits, electromagnetism, generators), "
            "thermal physics (heat transfer, gas laws), "
            "nuclear physics basics, modern physics introduction, "
            "optics (mirrors, lenses, refraction), "
            "measurement and experimental techniques"
        ),
        "History & Government": (
            "World history (ancient civilisations, world wars, Cold War), "
            "African history (kingdoms, colonialism, independence movements), "
            "Kenya's political history and constitution (2010), "
            "devolution and governance in Kenya, human rights, "
            "political systems comparison, international relations, "
            "Pan-Africanism, contemporary global issues"
        ),
        "Geography": (
            "Physical geography (landforms, climate, weather, plate tectonics), "
            "human geography (population, urbanisation, migration), "
            "Kenya's physical and human geography, economic geography, "
            "map work and GIS, fieldwork techniques, "
            "environmental management and sustainability, "
            "natural resources and energy, globalisation"
        ),
        "Business Studies": (
            "Macroeconomics (GDP, inflation, fiscal/monetary policy), "
            "microeconomics (supply/demand, market structures), "
            "accounting and financial statements, entrepreneurship, "
            "marketing strategies, international trade, "
            "banking and insurance, business law, "
            "office management, human resource management"
        ),
        "Computer Science": (
            "Programming (Python/Java), data structures and algorithms, "
            "databases and SQL, web development basics, "
            "networking fundamentals, cybersecurity awareness, "
            "operating systems, software development life cycle, "
            "AI and emerging technologies introduction"
        ),
        "Agriculture": (
            "Crop science (agronomy, horticulture), animal production, "
            "soil science and management, agricultural economics, "
            "farm mechanisation, water resources and irrigation, "
            "agricultural research methods, food technology, "
            "sustainable agriculture, climate-smart farming"
        ),
    },
}

# Default fallback for subjects not explicitly listed
_DEFAULT_CONTEXT = "General knowledge appropriate for the student's grade level in the Kenyan CBC curriculum."


def get_curriculum_context(grade: str, subject: str = "General") -> str:
    """Return curriculum context for a given grade and subject.

    Matches the student's grade string (e.g. 'Grade 5', 'PP1', 'Grade 10') to
    the appropriate CBC level band and returns the relevant topic expectations.
    """
    grade_lower = grade.lower().strip()

    # Determine which CBC band this grade falls into
    band = None

    # Check exact match in lookup table first
    for g, b in CBC_LEVELS:
        if g.lower() == grade_lower:
            band = b
            break

    # Fallback: pattern matching
    if not band:
        if "pp" in grade_lower or "pre" in grade_lower:
            band = "Pre-Primary"
        elif any(f"form {n}" in grade_lower for n in ("1", "2", "3", "4")):
            # Legacy Form 1-4 maps to Senior Secondary in CBC
            band = "Senior Secondary"
        else:
            nums = re.findall(r"\d+", grade)
            if nums:
                n = int(nums[0])
                if n <= 3:
                    band = "Lower Primary"
                elif n <= 6:
                    band = "Upper Primary"
                elif n <= 9:
                    band = "Junior Secondary"
                elif n <= 12:
                    band = "Senior Secondary"

    if not band:
        return _DEFAULT_CONTEXT

    subjects = CURRICULUM[band]

    # Try exact match first, then partial match
    subject_lower = subject.lower()
    for key, context in subjects.items():
        if key.lower() == subject_lower:
            return f"[{band} — {grade} / {key}] {context}"
    for key, context in subjects.items():
        if key.lower() in subject_lower or subject_lower in key.lower():
            return f"[{band} — {grade} / {key}] {context}"

    # Return all subjects as general context
    all_topics = "; ".join(f"{k}: {v}" for k, v in subjects.items())
    return f"[{band} — {grade}] {all_topics}"


def get_subjects_for_grade(grade: str) -> list[str]:
    """Return the list of CBC subjects (learning areas) available for a grade."""
    grade_lower = grade.lower().strip()

    band = None
    for g, b in CBC_LEVELS:
        if g.lower() == grade_lower:
            band = b
            break

    if not band:
        if "pp" in grade_lower or "pre" in grade_lower:
            band = "Pre-Primary"
        else:
            nums = re.findall(r"\d+", grade)
            if nums:
                n = int(nums[0])
                if n <= 3:
                    band = "Lower Primary"
                elif n <= 6:
                    band = "Upper Primary"
                elif n <= 9:
                    band = "Junior Secondary"
                elif n <= 12:
                    band = "Senior Secondary"

    if not band or band not in CURRICULUM:
        return []

    return list(CURRICULUM[band].keys())
