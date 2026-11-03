import os
import pygame as pg
import random
import sys
# スクリプトの保存先フォルダをカレントディレクトリに変更
os.chdir(os.path.dirname(os.path.abspath(__file__)))
WIDTH = 1100
HEIGHT = 650
FPS = 60
pg.init()
screen = pg.display.set_mode((WIDTH, HEIGHT))
pg.display.set_caption("こうかとんの杭打ち機回避ゲーム")
clock = pg.time.Clock()

def load_image_with_fallback(filenames):
    """実行環境に合わせて画像を探索"""
    for fname in filenames:
        candidates = [
            os.path.join("fig", fname),
            fname
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return pg.image.load(path)
                except Exception:
                    pass
    return None

# プレイヤー（こうかとん: 3.png）
class Player:
    def __init__(self):
        self.w = 65
        self.h = 65
        self.x = WIDTH // 2 - self.w // 2
        self.y = HEIGHT - 115
        self.normal_speed = 7.5
        self.boost_speed = 14.0
        self.rect = pg.Rect(self.x, self.y, self.w, self.h)
        self.facing_right = True
        raw_img = load_image_with_fallback(["3.png"])
        if raw_img:
            base_img = raw_img.convert_alpha()
            try:
                base_img = pg.transform.smoothscale(base_img, (self.w, self.h))
            except Exception:
                base_img = pg.transform.scale(base_img, (self.w, self.h))
        else:
            base_img = pg.Surface((self.w, self.h))
            base_img.fill((255, 200, 0))
        # 元画像(3.png)が左向きのため反転設定
        self.img_left = base_img
        self.img_right = pg.transform.flip(base_img, True, False)

    def update(self, shift_pressed):
        keys = pg.key.get_pressed()
        spd = self.boost_speed if shift_pressed else self.normal_speed
        if keys[pg.K_a] or keys[pg.K_LEFT]:
            self.x -= spd
            self.facing_right = False
        if keys[pg.K_d] or keys[pg.K_RIGHT]:
            self.x += spd
            self.facing_right = True
        self.x = max(0, min(self.x, WIDTH - self.w))
        self.rect.x = self.x

    def draw(self, target_surf):
        img = self.img_right if self.facing_right else self.img_left
        target_surf.blit(img, self.rect)

# 杭打ち機の壁（上からの登場スピード強化版）
class HammerWall:
    def __init__(self, base_speed):
        self.h = 165
        self.y = -self.h
        self.gap_w = 135
        self.gap_x = random.randint(80, WIDTH - 80 - self.gap_w)
        self.base_down_speed = base_speed
        self.down_speed = base_speed
        self.rise_speed = 12
        # ステート制御
        self.state = "warning"
        self.warning_speed = 3.2
        self.warning_target_y = 15
        self.hold_timer = 25
        self.ground_hold_timer = 20
        self.update_rects()

    def update_rects(self):
        self.left_rect = pg.Rect(0, self.y, self.gap_x, self.h)
        self.right_rect = pg.Rect(self.gap_x + self.gap_w, self.y, WIDTH - (self.gap_x + self.gap_w), self.h)

    def update(self):
        passed = False
        if self.state == "warning":
            self.y += self.warning_speed
            if self.y >= self.warning_target_y:
                self.state = "hold"
                self.timer = self.hold_timer
        elif self.state == "hold":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "falling"
                self.down_speed = self.base_down_speed
        elif self.state == "falling":
            self.y += self.down_speed
            self.down_speed += 2.5
            land_y = HEIGHT - self.h
            if self.y >= land_y:
                self.y = land_y
                self.state = "ground_hold"
                self.timer = self.ground_hold_timer
                passed = True
        elif self.state == "ground_hold":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "rising"
        elif self.state == "rising":
            self.y -= self.rise_speed
            if self.y <= -self.h:
                self.state = "warning"
                self.timer = self.hold_timer
                self.gap_x = random.randint(80, WIDTH - 80 - self.gap_w)
        self.update_rects()
        return passed

    def draw(self, target_surf):
        top_wall_height = max(0, int(self.y))
        if top_wall_height > 0:
            pg.draw.rect(target_surf, (80, 85, 100), (0, 0, WIDTH, top_wall_height))
        if self.y + self.h > 0:
            pg.draw.rect(target_surf, (80, 85, 100), self.left_rect)
            pg.draw.rect(target_surf, (80, 85, 100), self.right_rect)
            line_color = (255, 200, 0) if self.state in ["warning", "hold"] else (220, 60, 60)
            pg.draw.rect(target_surf, line_color, (0, self.left_rect.bottom - 8, self.gap_x, 8))
            pg.draw.rect(target_surf, line_color, (self.gap_x + self.gap_w, self.right_rect.bottom - 8, WIDTH - (self.gap_x + self.gap_w), 8))
            if self.y > 0:
                pg.draw.line(target_surf, (50, 55, 70), (self.gap_x, self.y), (self.gap_x + self.gap_w, self.y), 3)

    def collide(self, player_rect):
        return self.left_rect.colliderect(player_rect) or self.right_rect.colliderect(player_rect)

# 背景描画
def draw_background(target_surf, bg_img):
    if bg_img:
        target_surf.blit(bg_img, (0, 0))
    else:
        target_surf.fill((20, 24, 38))
        for x in range(0, WIDTH, 50):
            pg.draw.line(target_surf, (32, 38, 58), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, 50):
            pg.draw.line(target_surf, (32, 38, 58), (0, y), (WIDTH, y))

def main():
    player = Player()
    wall = HammerWall(base_speed=15.0)
    score = 0
    game_over = False

    # HP設定
    max_hp = 100
    hp = max_hp
    damage = 20
    invincible_timer = 0
    invincible_frame = 60  # 衝突後1秒無敵（連続ダメージ防止）

    canvas = pg.Surface((WIDTH, HEIGHT))
    big_shake_timer = 0
    raw_bg = load_image_with_fallback(["pg_bg.jpg", "background.jpg", "background.png"])
    if raw_bg:
        try:
            bg_img = pg.transform.smoothscale(raw_bg.convert(), (WIDTH, HEIGHT))
        except Exception:
            bg_img = pg.transform.scale(raw_bg.convert(), (WIDTH, HEIGHT))
    else:
        bg_img = None
    font = pg.font.SysFont(["meiryo", "hiraginosans", "yu gothic", "msgothic"], 36)

    while True:
        clock.tick(FPS)
        shift_pressed = pg.key.get_pressed()[pg.K_LSHIFT] or pg.key.get_pressed()[pg.K_RSHIFT]
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            # Rキーでリスタート
            if game_over and event.type == pg.KEYDOWN and event.key == pg.K_r:
                return main()

        if not game_over:
            player.update(shift_pressed)
            if wall.update():
                score += 1
                wall.base_down_speed = 15.0 + score * 0.5
                big_shake_timer = 10

            # 無敵時間カウント
            if invincible_timer > 0:
                invincible_timer -= 1

            # 衝突判定
            if wall.collide(player.rect) and invincible_timer <= 0:
                hp -= damage
                invincible_timer = invincible_frame
                if hp <= 0:
                    game_over = True

        draw_background(canvas, bg_img)
        wall.draw(canvas)
        player.draw(canvas)

        text_color = (30, 30, 30) if bg_img else (255, 255, 255)
        score_surf = font.render(f"Score: {score}", True, text_color)
        canvas.blit(score_surf, (20, 20))

        # HPバー描画
        bar_x = 20
        bar_y = 70
        bar_w = 200
        bar_h = 22
        pg.draw.rect(canvas, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))
        hp_ratio = hp / max_hp
        if hp_ratio > 0.5:
            hp_color = (0, 220, 0)
        elif hp_ratio > 0.25:
            hp_color = (220, 180, 0)
        else:
            hp_color = (220, 0, 0)
        pg.draw.rect(canvas, hp_color, (bar_x, bar_y, bar_w * hp_ratio, bar_h))
        pg.draw.rect(canvas, (255,255,255), (bar_x, bar_y, bar_w, bar_h), 2)
        hp_text = font.render(f"HP: {hp}/{max_hp}", True, text_color)
        canvas.blit(hp_text, (bar_x + bar_w + 10, bar_y))

        # GameOver文字
        if game_over:
            over_surf = font.render("GAME OVER! Rキーでリスタート", True, (255, 40, 40))
            canvas.blit(over_surf, (WIDTH//2 - 260, HEIGHT//2))

        # ---------------- 画面振動 ----------------
        offset_x = 0
        offset_y = 0
        if wall.state == "warning":
            offset_x = random.randint(-2, 2)
            offset_y = random.randint(-2, 2)
        elif wall.state == "hold":
            offset_x = random.randint(-10, 10)
            offset_y = random.randint(-10, 10)
        elif big_shake_timer > 0:
            big_shake_timer -= 1
            offset_x = random.randint(-8, 8)
            offset_y = random.randint(-8, 8)

        screen.fill((0, 0, 0))
        screen.blit(canvas, (offset_x, offset_y))
        pg.display.flip()

if __name__ == "__main__":
    main()
