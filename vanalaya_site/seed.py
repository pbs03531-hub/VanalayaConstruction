"""Starting content for the Vanalaya Studio website.

Everything here can be edited later from the admin panel.
Descriptions use only facts from the studio's Drive folder.
"""

CATEGORIES = [
    ("residential", "Residential", "Homes and farm houses designed and detailed from plan to finish."),
    ("commercial", "Commercial", "Schools, markets and workshops planned for everyday use."),
    ("eco-friendly", "Eco-friendly", "Bamboo, mud and sustainable construction that sits lightly on the land."),
    ("hospitality", "Hospitality", "Restaurants and resorts that make nature part of the experience."),
    ("interior-design", "Interior Design", "Interiors and handcrafted bamboo furniture."),
]

SERVICES = [
    ("Architecture Design", "Thoughtful building design shaped by the site, the climate and the way you live or work.", "home"),
    ("Interior Design", "Interiors that are warm, practical and detailed down to the ceilings, doors and furniture.", "sofa"),
    ("Landscape Design", "Gardens, courtyards and outdoor spaces that connect a building to its surroundings.", "leaf"),
    ("Layouts Planning", "Clear, efficient site and floor layouts that make the most of the plot.", "layers"),
    ("Sustainable Architecture Design", "Low-impact design using natural light, ventilation and renewable materials.", "sprout"),
    ("Mud and Bamboo Architecture", "Buildings in mud and bamboo that are beautiful, durable and kind to the environment.", "bamboo"),
    ("Bamboo Furniture and Products Design", "Handcrafted bamboo tables, chairs, counters and more, made to order.", "chair"),
    ("Architectural Conservation and Restoration", "Careful restoration that protects the character of older buildings.", "column"),
    ("Civil Engineering Services", "Building planning and design, structural analysis, supervision of infrastructure and building construction, MEP services, and sanction building plans and drawings.", "helmet"),
]

# slug, title, category, location, summary, description, tags, role, featured
PROJECTS = [
    ("basavraj-residence-gokak", "Basavraj Residence, Gokak", "residential", "Gokak",
     "A complete home designed and detailed by the studio, from planning and structure to plumbing, doors and windows.",
     "A complete home designed and detailed by the studio, from planning and structure to plumbing, doors and windows, with a custom home theatre and a landscaped garden.\n\nThe ground floor is planned around a family lounge, living and dining spaces, bedrooms with attached bathrooms, a pooja room and a garden, with a sit-out at the entrance.",
     "residential,architecture,interior", "Architecture, interior design, structural and services drawings", 1),
    ("bamboo-wall-farm-house-morwa", "Bamboo Wall Work, Farm House, Morwa Village", "residential", "Morwa Village, Chandrapur",
     "Natural bamboo walls that give a farm house warmth, character and a light footprint.",
     "Natural bamboo walls that give a farm house warmth, character and a light footprint.",
     "bamboo,eco,farm house", "Bamboo construction", 0),
    ("h-anjaneya-school", "H. Anjaneya School", "commercial", "",
     "A multi-storey school with a basement and four floors, planned around bright classrooms, safe circulation, a stage and sports space.",
     "A multi-storey school with a basement and four floors, planned around bright classrooms, safe circulation, a stage and sports space.\n\nThe design includes classrooms for the early years, a staff room, a first aid room, a dining and recreation area, toilets and a landscaped courtyard, supported by a complete set of architectural, structural and services drawings.",
     "school,institutional,architecture", "Architecture, structural and services drawings", 1),
    ("rural-haat-dandeli", "Rural Haat, Dandeli", "commercial", "Dandeli",
     "A rural market concept developed through three design options and a walkthrough.",
     "A rural market concept developed through three design options and a walkthrough, shaped around local trade and open public spaces.",
     "market,design options,walkthrough", "Concept design and 3D walkthrough", 1),
    ("workshop-infrastructure-chichpalli", "Workshop Infrastructure, Jambharla Village", "commercial", "Jambharla Village, near Chichpalli, Chandrapur",
     "A 6,000 sq ft workshop planned on a two-acre site.",
     "A 6,000 sq ft workshop planned on a two-acre site, organised for efficient work and everyday practical use.",
     "workshop,infrastructure", "Planning and design", 0),
    ("bamboo-construction-brtc-chichpalli", "Bamboo Construction, BRTC Campus", "eco-friendly", "BRTC Campus, Chichpalli",
     "Bamboo construction within a working campus.",
     "Bamboo construction within a working campus, showing how a sustainable material can serve institutional needs.",
     "bamboo,eco,campus", "Bamboo construction", 1),
    ("bamboo-machan-gadchiroli", "Bamboo Machan, Forest Garden", "eco-friendly", "Gadchiroli",
     "An elevated bamboo machan that blends into the forest garden.",
     "An elevated bamboo machan that blends into the forest garden and offers a calm vantage point.",
     "bamboo,eco,forest", "Bamboo construction", 0),
    ("bamboo-gazebo-forest-garden-gadchiroli", "Bamboo Gazebo, Forest Garden", "eco-friendly", "Gadchiroli",
     "A bamboo gazebo that gives visitors shaded shelter in a natural setting.",
     "A bamboo gazebo that gives visitors shaded shelter in a natural setting.",
     "bamboo,eco,gazebo", "Bamboo construction", 0),
    ("bamboo-gate-forest-garden-gadchiroli", "Bamboo Gate, Forest Garden", "eco-friendly", "Gadchiroli",
     "A handcrafted bamboo entrance in keeping with its green surroundings.",
     "A handcrafted bamboo entrance that welcomes visitors in keeping with its green surroundings.",
     "bamboo,eco,gate", "Bamboo construction", 0),
    ("bamboo-gazebo-asst-collector-bungalow", "Bamboo Gazebo, Assistant Collector Bungalow", "eco-friendly", "Gadchiroli",
     "A bamboo gazebo that adds a quiet outdoor sitting space to an official residence.",
     "A bamboo gazebo that adds a quiet outdoor sitting space to an official residence.",
     "bamboo,eco,gazebo", "Bamboo construction", 0),
    ("bamboo-tree-guards-forest-department", "Eco-friendly Bamboo Tree Guards", "eco-friendly", "For the Forest Department",
     "Durable bamboo tree guards made for the Forest Department.",
     "Durable bamboo tree guards made for the Forest Department to protect young plantations, using a renewable material.",
     "bamboo,eco,forest department", "Bamboo products", 0),
    ("resort-entrance-gate-mamla", "Resort Entrance Gate, Mamla Village", "hospitality", "Mamla Village (TATR buffer), Chandrapur",
     "A bamboo entrance gate that sets the nature-led tone of the resort.",
     "A bamboo entrance gate that sets the nature-led tone of the resort from the first step.",
     "bamboo,gate,resort", "Bamboo construction", 1),
    ("bamboo-restaurant-rastrawadi-nagar", "Bamboo Restaurant, Rastrawadi Nagar", "hospitality", "Rastrawadi Nagar, Chandrapur",
     "A bamboo restaurant with an earthy, welcoming atmosphere.",
     "A bamboo restaurant with an earthy, welcoming atmosphere and a distinct identity.",
     "bamboo,restaurant,eco", "Architecture and bamboo construction", 1),
    ("bamboo-gate-counter-rastrawadi-nagar", "Bamboo Gate and Counter, Rastrawadi Nagar Restaurant", "hospitality", "Rastrawadi Nagar, Chandrapur",
     "A matching bamboo entrance and service counter.",
     "A matching bamboo entrance and service counter that complete the restaurant's character.",
     "bamboo,gate,counter", "Bamboo construction and furniture", 0),
    ("bamboo-counters-hotels", "Bamboo Counters for Hotels", "interior-design", "",
     "Handcrafted bamboo counters for hotel reception and service areas.",
     "Handcrafted bamboo counters that give hotel reception and service areas a warm, natural finish.",
     "bamboo,furniture,hotel", "Bamboo furniture design", 0),
    ("eco-friendly-bamboo-tables", "Eco-friendly Bamboo Tables", "interior-design", "",
     "Bamboo tables that pair strength and clean lines with a renewable material.",
     "Bamboo tables that pair strength and clean lines with a renewable material.",
     "bamboo,furniture,tables", "Bamboo furniture design", 0),
    ("relaxing-bamboo-chairs", "Relaxing Bamboo Chairs", "interior-design", "",
     "Comfortable bamboo chairs designed for relaxed, everyday seating.",
     "Comfortable bamboo chairs designed for relaxed, everyday seating.",
     "bamboo,furniture,chairs", "Bamboo furniture design", 0),
    ("bamboo-dining-table-chairs", "Bamboo Dining Table and Chairs", "interior-design", "",
     "A custom bamboo dining set made for the residence of an IPS officer.",
     "A custom bamboo dining set made for the residence of an IPS officer.",
     "bamboo,furniture,dining", "Bamboo furniture design", 0),
    ("home-theatre-basavraj-residence", "Home Theatre, Basavraj Residence", "interior-design", "Gokak",
     "A custom home theatre designed for comfortable viewing.",
     "A custom home theatre designed with detailed layouts, a false ceiling and elevations for comfortable viewing.",
     "interior,home theatre", "Interior design", 0),
]

SETTINGS = {
    "studio_name": "Vanalaya Studio",
    "tagline": "Architecture rooted in nature",
    "hero_headline": "Architecture that belongs to the land",
    "hero_sub": "Architecture, interiors and civil engineering from Coorg, with a special craft in mud and bamboo.",
    "about_title": "Design that listens to the land",
    "about_text": (
        "Vanalaya Studio is an architecture and civil engineering studio based in Virajpet, Coorg. "
        "We design and build homes, schools, markets, restaurants and resorts, and we have a special "
        "craft in mud and bamboo architecture and in handmade bamboo furniture.\n\n"
        "Our work starts with the site: its light, its climate and its materials. From there we plan, "
        "design, detail and supervise construction, so that what you approve on paper is what gets built.\n\n"
        "From concept sketches to sanction drawings, structural analysis and MEP services, everything is "
        "handled under one roof."
    ),
    "founder_name": "Ar. Viniya",
    "founder_role": "Architect and founder",
    "founder_text": "Ar. Viniya leads the studio's architecture, interior and sustainable design work.",
    "eco_title": "Built with bamboo, mud and respect for the land",
    "eco_text": (
        "Bamboo grows fast, is strong and renews itself. Mud keeps buildings cool and is available on site. "
        "We use these materials, together with careful orientation and natural ventilation, to create "
        "buildings that are comfortable, long-lasting and light on the environment."
    ),
    "phone": "8310347635",
    "whatsapp": "918310347635",
    "email": "vanalaya.architecture.studio@gmail.com",
    "address": "Virajpet, Coorg",
    "instagram": "vanalaya.architecture.studio",
    "cta_text": "Get a free consultation",
}

APPROACH = [
    ("Listen", "We start with a conversation about your needs, your plot and your budget."),
    ("Plan", "Layouts and concept sketches that you can review and refine with us."),
    ("Design", "Detailed architecture, interior and structural drawings, ready for approval and sanction."),
    ("Build", "Construction supervision and MEP coordination so the work matches the drawings."),
    ("Handover", "A finished space that is ready to use and true to the approved design."),
]
