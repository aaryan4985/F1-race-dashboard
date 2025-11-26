import os
import arcade
import numpy as np

# Default starting sizes (window is resizable)
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1200
SCREEN_TITLE = "F1 Replay"


def build_track_from_example_lap(example_lap, track_width=200):
    """Build inner/outer track boundaries from an example lap."""
    plot_x_ref = example_lap["X"].to_numpy()
    plot_y_ref = example_lap["Y"].to_numpy()

    # Compute tangents
    dx = np.gradient(plot_x_ref)
    dy = np.gradient(plot_y_ref)

    norm = np.sqrt(dx**2 + dy**2)
    norm[norm == 0] = 1.0
    dx /= norm
    dy /= norm

    # Normal vectors
    nx = -dy
    ny = dx

    # Offset for inner and outer edges
    x_outer = plot_x_ref + nx * (track_width / 2)
    y_outer = plot_y_ref + ny * (track_width / 2)
    x_inner = plot_x_ref - nx * (track_width / 2)
    y_inner = plot_y_ref - ny * (track_width / 2)

    # World bounds
    x_min = min(plot_x_ref.min(), x_inner.min(), x_outer.min())
    x_max = max(plot_x_ref.max(), x_inner.max(), x_outer.max())
    y_min = min(plot_y_ref.min(), y_inner.min(), y_outer.min())
    y_max = max(plot_y_ref.max(), y_inner.max(), y_outer.max())

    return (
        plot_x_ref,
        plot_y_ref,
        x_inner,
        y_inner,
        x_outer,
        y_outer,
        x_min,
        x_max,
        y_min,
        y_max,
    )


class F1ReplayWindow(arcade.Window):
    def __init__(self, frames, example_lap, drivers, title,
                 playback_speed=1.0, driver_colors=None):
        # Resizable window so user can adjust mid-sim
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, title, resizable=True)

        self.frames = frames
        self.n_frames = len(frames)
        self.drivers = list(drivers)
        self.playback_speed = playback_speed
        self.driver_colors = driver_colors or {}
        self.frame_index = 0
        self.paused = False

        # Build track geometry (world coordinates)
        (
            self.plot_x_ref,
            self.plot_y_ref,
            self.x_inner,
            self.y_inner,
            self.x_outer,
            self.y_outer,
            self.x_min,
            self.x_max,
            self.y_min,
            self.y_max,
        ) = build_track_from_example_lap(example_lap)

        # Pre-calculate interpolated world points ONCE (optimization)
        self.world_inner_points = self._interpolate_points(self.x_inner, self.y_inner)
        self.world_outer_points = self._interpolate_points(self.x_outer, self.y_outer)

        # Screen-space points (updated when window resizes)
        self.screen_inner_points = []
        self.screen_outer_points = []

        # Scaling parameters
        self.world_scale = 1.0
        self.tx = 0
        self.ty = 0

        # Optional background image
        bg_path = os.path.join("resources", "background.png")
        self.bg_texture = arcade.load_texture(bg_path) if os.path.exists(bg_path) else None

        # Fallback background color
        arcade.set_background_color(arcade.color.BLACK)

        # Initial scaling
        self.update_scaling(self.width, self.height)

    def _interpolate_points(self, xs, ys, interp_points=2000):
        """Generate smooth points in WORLD coordinates."""
        t_old = np.linspace(0, 1, len(xs))
        t_new = np.linspace(0, 1, interp_points)
        xs_i = np.interp(t_new, t_old, xs)
        ys_i = np.interp(t_new, t_old, ys)
        return list(zip(xs_i, ys_i))

    def update_scaling(self, screen_w, screen_h):
        """
        Recalculate scale and translation to fit the track
        within the screen while maintaining aspect ratio.
        """
        padding = 0.05
        world_w = max(1.0, self.x_max - self.x_min)
        world_h = max(1.0, self.y_max - self.y_min)

        usable_w = screen_w * (1 - 2 * padding)
        usable_h = screen_h * (1 - 2 * padding)

        # Scale based on limiting dimension
        scale_x = usable_w / world_w
        scale_y = usable_h / world_h
        self.world_scale = min(scale_x, scale_y)

        # Center in screen
        world_cx = (self.x_min + self.x_max) / 2
        world_cy = (self.y_min + self.y_max) / 2
        screen_cx = screen_w / 2
        screen_cy = screen_h / 2

        self.tx = screen_cx - self.world_scale * world_cx
        self.ty = screen_cy - self.world_scale * world_cy

        # Update screen coordinates of track polylines
        self.screen_inner_points = [self.world_to_screen(x, y) for x, y in self.world_inner_points]
        self.screen_outer_points = [self.world_to_screen(x, y) for x, y in self.world_outer_points]

    def on_resize(self, width, height):
        """Called automatically by Arcade when window is resized."""
        super().on_resize(width, height)
        self.update_scaling(width, height)

    def world_to_screen(self, x, y):
        """Convert world coordinates to screen coordinates."""
        sx = self.world_scale * x + self.tx
        sy = self.world_scale * y + self.ty
        return sx, sy

    def draw_timeline(self, frame):
        """Draw a simple race progress bar at the bottom."""
        margin_x = 80
        bar_y = 30
        bar_height = 6

        # Background line
        arcade.draw_line(
            margin_x,
            bar_y,
            self.width - margin_x,
            bar_y,
            arcade.color.DARK_GRAY,
            bar_height,
        )

        if self.n_frames > 1:
            progress = self.frame_index / (self.n_frames - 1)
        else:
            progress = 0.0

        knob_x = margin_x + progress * (self.width - 2 * margin_x)

        # Progress knob
        arcade.draw_circle_filled(knob_x, bar_y, 8, arcade.color.WHITE)

        # Playback speed info
        speed_text = f"{self.playback_speed:.1f}x"
        arcade.draw_text(
            f"Speed: {speed_text}",
            margin_x,
            bar_y + 14,
            arcade.color.LIGHT_GRAY,
            12,
        )

    def on_draw(self):
        self.clear()

        # 1. Background (image if available, else fallback color already set)
        if self.bg_texture:
            arcade.draw_lrbt_rectangle_textured(
                left=0,
                right=self.width,
                bottom=0,
                top=self.height,
                texture=self.bg_texture,
            )

        # 2. Track (using pre-calculated screen points)
        track_color = (150, 150, 150)
        if len(self.screen_inner_points) > 1:
            arcade.draw_line_strip(self.screen_inner_points, track_color, 4)
        if len(self.screen_outer_points) > 1:
            arcade.draw_line_strip(self.screen_outer_points, track_color, 4)

        # Start/finish line using first inner/outer points
        if self.screen_inner_points and self.screen_outer_points:
            (sx1, sy1) = self.screen_inner_points[0]
            (sx2, sy2) = self.screen_outer_points[0]
            arcade.draw_line(sx1, sy1, sx2, sy2, arcade.color.WHITE, 3)

        # 3. Cars
        frame = self.frames[self.frame_index]
        for code, pos in frame["drivers"].items():
            # rel_dist == 1 used here to indicate car is out / finished
            if pos.get("rel_dist", 0) == 1:
                continue

            sx, sy = self.world_to_screen(pos["x"], pos["y"])
            color = self.driver_colors.get(code, arcade.color.WHITE)

            # Outer ring for contrast
            arcade.draw_circle_filled(sx, sy, 8, arcade.color.BLACK)
            # Inner body with team color
            arcade.draw_circle_filled(sx, sy, 6, color)

            # Tiny driver code label
            arcade.draw_text(
                code,
                sx + 10,
                sy + 4,
                arcade.color.WHITE,
                10,
                anchor_x="left",
                anchor_y="bottom",
            )

        # --- UI ELEMENTS (HUD, Leaderboard, Controls, Timeline) ---

        # Leader info
        leader_code = max(
            frame["drivers"],
            key=lambda c: (
                frame["drivers"][c].get("lap", 1),
                frame["drivers"][c].get("dist", 0),
            ),
        )
        leader_lap = frame["drivers"][leader_code].get("lap", 1)

        # Time calculation
        t = frame["t"]
        hours = int(t // 3600)
        minutes = int((t % 3600) // 60)
        seconds = int(t % 60)
        time_str = f"{hours:02}:{minutes:02}:{seconds:02}"

        # === TOP-LEFT HUD (Lap + Race Time) ===
        hud_bg_width = 260
        hud_bg_height = 80
        hud_bg_x = 20 + hud_bg_width / 2
        hud_bg_y = self.height - 20 - hud_bg_height / 2

        arcade.draw_lrbt_rectangle_filled(
            left=hud_bg_x - hud_bg_width / 2,
            right=hud_bg_x + hud_bg_width / 2,
            bottom=hud_bg_y - hud_bg_height / 2,
            top=hud_bg_y + hud_bg_height / 2,
            color=(10, 10, 20, 210),  # semi-transparent dark
        )

        arcade.draw_text(
            f"Lap {leader_lap}",
            hud_bg_x - hud_bg_width / 2 + 12,
            hud_bg_y + 18,
            arcade.color.WHITE,
            20,
        )

        arcade.draw_text(
            f"Race: {time_str}",
            hud_bg_x - hud_bg_width / 2 + 12,
            hud_bg_y - 8,
            arcade.color.LIGHT_GRAY,
            14,
        )

        # === LEADERBOARD PANEL (Right side) ===
        panel_width = 260
        panel_height = min(400, self.height - 80)
        panel_x = self.width - panel_width / 2 - 20
        panel_y = self.height - panel_height / 2 - 20

        arcade.draw_lrbt_rectangle_filled(
            left=panel_x - panel_width / 2,
            right=panel_x + panel_width / 2,
            bottom=panel_y - panel_height / 2,
            top=panel_y + panel_height / 2,
            color=(5, 5, 15, 220),
        )

        arcade.draw_text(
            "LEADERBOARD",
            panel_x - panel_width / 2 + 12,
            panel_y + panel_height / 2 - 32,
            arcade.color.WHITE,
            16,
            bold=True,
        )

        driver_list = []
        for code, pos in frame["drivers"].items():
            color = self.driver_colors.get(code, arcade.color.WHITE)
            driver_list.append((code, color, pos))

        # Sort by distance (leader first)
        driver_list.sort(key=lambda x: x[2].get("dist", 999), reverse=True)

        row_y = panel_y + panel_height / 2 - 60
        row_height = 22

        for i, (code, color, pos) in enumerate(driver_list):
            current_pos = i + 1
            if pos.get("rel_dist", 0) == 1:
                text = f"{current_pos:>2}. {code}   OUT"
            else:
                text = f"{current_pos:>2}. {code}"

            arcade.draw_text(
                text,
                panel_x - panel_width / 2 + 12,
                row_y - i * row_height,
                color,
                14,
            )

        # === CONTROLS LEGEND (Bottom-left panel) ===
        legend_width = 320
        legend_height = 110
        legend_x = 20 + legend_width / 2
        legend_y = 60

        arcade.draw_lrbt_rectangle_filled(
            left=legend_x - legend_width / 2,
            right=legend_x + legend_width / 2,
            bottom=legend_y - legend_height / 2,
            top=legend_y + legend_height / 2,
            color=(5, 5, 15, 220),
        )

        legend_lines = [
            "Controls",
            "[SPACE]  Pause / Resume",
            "[←/→]    Step backward / forward",
            "[↑/↓]    Adjust speed",
            "[1-4]    0.5x / 1x / 2x / 4x",
        ]

        for i, line in enumerate(legend_lines):
            arcade.draw_text(
                line,
                legend_x - legend_width / 2 + 12,
                legend_y + legend_height / 2 - 28 - i * 18,
                arcade.color.LIGHT_GRAY if i > 0 else arcade.color.WHITE,
                13,
                bold=(i == 0),
            )

        # === TIMELINE / PROGRESS BAR (Bottom) ===
        self.draw_timeline(frame)

    def on_update(self, delta_time: float):
        if self.paused:
            return

        step = max(1, int(self.playback_speed))
        self.frame_index += step

        if self.frame_index >= self.n_frames:
            self.frame_index = self.n_frames - 1

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.SPACE:
            self.paused = not self.paused
        elif symbol == arcade.key.RIGHT:
            self.frame_index = min(self.frame_index + 10, self.n_frames - 1)
        elif symbol == arcade.key.LEFT:
            self.frame_index = max(self.frame_index - 10, 0)
        elif symbol == arcade.key.UP:
            self.playback_speed *= 2.0
        elif symbol == arcade.key.DOWN:
            self.playback_speed = max(0.1, self.playback_speed / 2.0)
        elif symbol == arcade.key.KEY_1:
            self.playback_speed = 0.5
        elif symbol == arcade.key.KEY_2:
            self.playback_speed = 1.0
        elif symbol == arcade.key.KEY_3:
            self.playback_speed = 2.0
        elif symbol == arcade.key.KEY_4:
            self.playback_speed = 4.0


def run_arcade_replay(frames, example_lap, drivers, title,
                      playback_speed=1.0, driver_colors=None):
    """Convenience function to run the F1 replay window."""
    window = F1ReplayWindow(
        frames=frames,
        example_lap=example_lap,
        drivers=drivers,
        playback_speed=playback_speed,
        driver_colors=driver_colors,
        title=title,
    )
    arcade.run()