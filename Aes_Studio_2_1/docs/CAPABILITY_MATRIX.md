# Capability Matrix

This maps the requested “one AI that can do everything” categories to actual Aes components.

| Capability | Aes component | What is executable today | What still needs an installed local engine/app |
|---|---|---|---|
| Device / OS control | Device & Systems skill + computer tools | Screenshot, mouse, keyboard, app launch with permission | Better visual grounding / multimodal model |
| Professional coding | Coding skill + agent loop + Git + command tools | Read/search/edit/test/diff, backups, sub-agent review | Language-specific toolchains must be installed |
| Games & apps | Games & Apps skill | Project coding/build commands | Unity/Android/etc. must be installed |
| 3D | 3D Modeling skill | Write/run Blender Python scripts | Blender installed/configured |
| Roblox | Roblox Creator skill | Luau/project edits and Rojo build | Rojo/Studio workflow installed |
| Media editing | Media Production skill | Plans/scripts/file automation | FFmpeg/NLE integrations if desired |
| Daily assistant | Daily Assistant + memory | Persistent notes/context and project organization | Calendar/email integrations not bundled |
| Research | Research skill + knowledge + fetch URL | Private docs + direct URL reading | Search-provider plugin for broad web search |
| Writing | Writing skill | Draft/edit local files | — |
| Visual design | Visual Design skill | UI/UX critique and implementation code | Local design/image tools for rendered assets |
| Science/engineering | Science skill + command tool | Code-assisted calculations and files | Domain simulators if required |
| Robotics/automation | Automation skill + command/files/network | Scripts, bots, workflows | Hardware/vendor SDKs |
| AI image/video | AI Image & Video skill | Workflow orchestration/config files | ComfyUI/SD/video model plugin |
| Audio/music | Audio skill | Workflow/scripts | DAW/audio engine integration |

The model's competence in each category depends strongly on the selected local base model and the quality of Aes-specific fine-tuning/evaluation data.
