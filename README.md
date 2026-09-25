# Autonomous Historical Battle Video Pipeline

An end-to-end, production-grade video generation engine designed for GitHub Actions. It autonomously transforms narrative battle scripts into premium, minimalist tactical map videos (reminiscent of *Kings and Generals* and *Historic Battles*), muxes contextual sound effects, and uploads the final render to Google Drive.

---

## 🛡️ Core Visual Rule: Strict Aniconism
The video engine strictly enforces **ANICONISM**:
- **Zero depictions of living creatures**: No humans, no animals, no portraits, and no soldier models.
- Armies and skirmishes are visualized **exclusively** through NATO tactical unit symbols (blocks, slashes, chevrons), dynamic Bezier flanking arrows, frontline clash rings, and topographic grids.

---

## ⚙️ Architectural Workflow

```text
Google Drive (Script.txt / Audio) ──► rclone pull
                                         │
               ┌─────────────────────────┴────────────────────────┐
               ▼                                                   ▼
     Audio already exists?                             No audio found
               │                                                   │
               │                                   Language Detection (EN vs BN)
               │                                        │                 │
               │                             Kokoro TTS (EN)        Gemini TTS (BN)
               │                                        │                 │
               └─────────────────────────┬──────────────┴─────────────────┘
                                         ▼
                   Ollama Cloud (Multi-Key Rotation)
               Generates Timeline JSON & Geometric Moves
                                         │
                                         ▼
                         Manim Community 60FPS Render
               (Abstract Military Blocks, Arrows, Topography)
                                         │
                                         ▼
                      Procedural / Dynamic SFX Layering
                     (War Drums, Clashing, Marching, Wind)
                                         │
                                         ▼
                           FFmpeg Lossless Muxing (1080p)
                                         │
                                         ▼
                        rclone push ──► Google Drive
