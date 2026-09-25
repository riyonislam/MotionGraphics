"""
modules/battle_renderer.py
Historical Battle Cartography Engine (Circle/Star Particle Style).
Strict Aniconism: 100% Procedural & Code-Driven.
Renders White/Black troop dots, glowing commander stars, formations, and desert maps.
"""

from manim import *
import json
from pathlib import Path
from typing import List, Dict, Any

config.pixel_width = 1920
config.pixel_height = 1080
config.frame_rate = 60
config.background_color = "#c8b28a"  # Warm desert parchment tone


class TroopDot(Circle):
    """Abstract soldier representation: A bold circle."""
    def __init__(self, faction: str = "white", radius: float = 0.12, **kwargs):
        fill = "#FFFFFF" if faction == "white" else "#1A1A1A"
        stroke = "#000000"
        super().__init__(
            radius=radius,
            fill_color=fill,
            fill_opacity=1.0,
            stroke_color=stroke,
            stroke_width=2.5,
            **kwargs
        )


class CommanderStar(VGroup):
    """Abstract leader/general representation: Glowing Star."""
    def __init__(self, color: str = "#FFFFFF", radius: float = 0.35, **kwargs):
        super().__init__(**kwargs)
        # Inner Star
        self.star = Star(
            n=5,
            outer_radius=radius,
            inner_radius=radius * 0.48,
            color="#000000",
            fill_color=color,
            fill_opacity=1.0,
            stroke_width=2.5
        )
        # Outer luminous glow pulse
        self.glow = Annulus(
            inner_radius=radius * 0.8,
            outer_radius=radius * 1.5,
            fill_color=color,
            fill_opacity=0.35,
            stroke_width=0
        )
        self.add(self.glow, self.star)


class TacticalBattleScene(MovingCameraScene):
    def construct(self):
        plan_file = Path("./workspace/battle_plan.json")
        if not plan_file.exists():
            return

        with open(plan_file, "r", encoding="utf-8") as f:
            scenes_data: List[Dict[str, Any]] = json.load(f)

        # 1. Base Terrain / Desert Parchment Vignette
        vignette = Rectangle(
            width=16, height=9,
            fill_color="#000000", fill_opacity=0.12, stroke_width=0
        )
        self.add(vignette)

        # Tactical Formations Registry: {group_id: VGroup}
        armies: Dict[str, VGroup] = {}

        for scene in scenes_data:
            duration = float(scene.get("duration", 6.0))
            camera_data = scene.get("camera_focus", {})

            # Dynamic Camera Adjustments (Pan & Zoom into clusters)
            cam_anims = []
            if "pos" in camera_data:
                cam_anims.append(self.camera.frame.animate.move_to(camera_data["pos"]))
            if "zoom" in camera_data:
                cam_anims.append(self.camera.frame.animate.set(width=16 * camera_data["zoom"]))

            # Spawn Units (Grid lines, rings, or clusters of dots)
            spawn_anims = []
            for unit_group in scene.get("formations", []):
                gid = unit_group["id"]
                if gid not in armies:
                    faction = unit_group.get("faction", "white")  # "white" or "black"
                    shape = unit_group.get("shape", "line")        # "line", "circle", "wedge"
                    count = int(unit_group.get("count", 15))
                    has_commander = unit_group.get("has_commander", False)

                    formation = VGroup()

                    # Formation Geometry
                    if shape == "line":
                        cols = 10
                        for i in range(count):
                            r = i // cols
                            c = i % cols
                            d = TroopDot(faction=faction).move_to([c * 0.32, -r * 0.32, 0])
                            formation.add(d)

                    elif shape == "circle":
                        for i in range(count):
                            angle = i * (TAU / count)
                            d = TroopDot(faction=faction).move_to([np.cos(angle)*1.0, np.sin(angle)*1.0, 0])
                            formation.add(d)

                    elif shape == "scatter":
                        np.random.seed(42)
                        for _ in range(count):
                            rand_pos = np.random.uniform(-0.8, 0.8, 3)
                            rand_pos[2] = 0
                            formation.add(TroopDot(faction=faction).move_to(rand_pos))

                    # Center commander star if assigned
                    if has_commander:
                        star_color = "#FFFFFF" if faction == "white" else "#F59E0B"
                        commander = CommanderStar(color=star_color).move_to(formation.get_center())
                        formation.add(commander)

                    formation.move_to(unit_group.get("pos", [0, 0, 0]))
                    armies[gid] = formation
                    spawn_anims.append(FadeIn(formation, scale=0.9))

            if spawn_anims or cam_anims:
                self.play(*(spawn_anims + cam_anims), run_time=1.0)

            # Maneuver Actions (Clashing, Encirclement, Retreat)
            action_anims = []
            for act in scene.get("actions", []):
                act_type = act.get("type")
                gid = act.get("formation_id")

                if act_type == "move" and gid in armies:
                    action_anims.append(armies[gid].animate.move_to(act.get("target", [0, 0, 0])))

                elif act_type == "surround" and gid in armies:
                    # Animate dots expanding into a ring around target
                    center = act.get("center", [0, 0, 0])
                    for idx, dot in enumerate(armies[gid]):
                        angle = idx * (TAU / len(armies[gid]))
                        target_dot_pos = center + np.array([np.cos(angle)*1.4, np.sin(angle)*1.4, 0])
                        action_anims.append(dot.animate.move_to(target_dot_pos))

                elif act_type == "clash":
                    # Flash & slight vibration of colliding armies
                    action_anims.append(self.camera.frame.animate.scale(0.97))

            play_time = min(duration - 0.5, 3.5)
            if action_anims:
                self.play(*action_anims, run_time=play_time)

            # Hold for narration duration
            self.wait(max(0.5, duration - play_time - 1.0))
