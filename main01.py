import os
import random
import sys
import pygame as pg

WIDTH = 1100
HEIGHT = 650
FPS = 60

# ファイルの基準ディレクトリを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

pg.init()
pg.mixer.init()

screen = pg.display.set_mode((WIDTH, HEIGHT))
pg.display.set_caption("逃げろ工科トン")
clock = pg.time.Clock()


# ==================== 音声・画像の読み込み補助関数 ====================
def load_sound_safe(filename, volume=1.0):
    """効果音ファイルの安全な読み込み（存在しない場合はNone）"""
    path = os.path.join(BASE_DIR, "sound", filename)
    if os.path.exists(path):
        try:
            snd = pg.mixer.Sound(path)
            snd.set_volume(volume)
            return snd
        except Exception:
            pass
    return None


def play_bgm_safe(filename, volume=0.3):
    """BGMファイルの安全な読み込みとループ再生"""
    path = os.path.join(BASE_DIR, "sound", filename)
    if os.path.exists(path):
        try:
            pg.mixer.music.load(path)
            pg.mixer.music.set_volume(volume)
            pg.mixer.music.play(-1)
        except Exception:
            pass


def load_image_with_fallback(filenames):
    """実行環境に合わせて画像を探索"""
    for fname in filenames:
        candidates = [
            os.path.join(BASE_DIR, "fig", fname),
            os.path.join(BASE_DIR, fname),
            fname,
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return pg.image.load(path)
                except Exception:
                    pass
    return None


# ==================== HP管理クラス ====================
class HpManager:
    """HP/無敵時間/描画/フラッシュ演出を統合管理するクラス"""
    # プレイヤー（こうかとん: 3.png）
    def __init__(self, max_hp: int, damage: int, invincible_frame: int) -> None:
        self.max_hp = max_hp
        self.hp = max_hp
        self.damage = damage
        self.invincible_frame = invincible_frame
        self.invincible_timer = 0
        self.hit_flash_timer = 0

    def update(self) -> None:
        """無敵時間と被弾フラッシュタイマーの更新"""
        if self.invincible_timer > 0:
            self.invincible_timer -= 1
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= 1

    def take_damage(self) -> bool:
        """ダメージを受ける処理（実際に受傷したら True を返す）"""
        if self.invincible_timer <= 0:
            self.hp -= self.damage
            self.invincible_timer = self.invincible_frame
            self.hit_flash_timer = 12
            if self.hp < 0:
                self.hp = 0
            return True
        return False

    def heal(self, amount: int) -> None:
        """HPを回復する処理"""
        self.hp = min(self.max_hp, self.hp + amount)

    def is_dead(self) -> bool:
        """死亡判定"""
        return self.hp <= 0

    def draw(
        self, target_surf: pg.Surface, font: pg.font.Font, text_color: tuple
    ) -> None:
        """HPバーおよびテキスト描画"""
        bar_x = 20
        bar_y = 70
        bar_w = 200
        bar_h = 22
        pg.draw.rect(target_surf, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))

        hp_ratio = self.hp / self.max_hp
        if hp_ratio > 0.5:
            hp_color = (0, 220, 0)
        elif hp_ratio > 0.25:
            hp_color = (220, 180, 0)
        else:
            hp_color = (220, 0, 0)

        pg.draw.rect(
            target_surf, hp_color, (bar_x, bar_y, bar_w * hp_ratio, bar_h)
        )
        pg.draw.rect(
            target_surf, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h), 2
        )
        hp_text = font.render(f"HP: {self.hp}/{self.max_hp}", True, text_color)
        target_surf.blit(hp_text, (bar_x + bar_w + 10, bar_y))


# ----------------------------------------------------
# プレイヤー（こうかとん）クラス
# ----------------------------------------------------
class Player:
    """プレイヤーの移動・ジャンプ・しゃがみ状態を管理するクラス"""

    def __init__(self, char_type="koukaton") -> None:
        self.char_type = char_type
        self.w: int = 65
        self.base_h: int = 65  # 通常時の高さ
        self.h: int = self.base_h
        self.x: float = WIDTH // 2 - self.w // 2
        self.base_y: float = HEIGHT - 115  # 地上の初期Y座標
        self.y: float = self.base_y

        self.normal_speed: float = 7.5
        self.boost_speed: float = 14.0

        # ジャンプ・しゃがみ用パラメータ
        self.is_jumping: bool = False
        self.jump_power: float = -20.0
        self.gravity: float = 1.2
        self.vy: float = 0.0

        self.is_crouching: bool = False
        self.speed_timer: int = 0
        self.small_timer: int = 0

        self.rect: pg.Rect = pg.Rect(self.x, self.y, self.w, self.h)
        self.facing_right: bool = True

        filenames = ["man.png"] if char_type == "man" else ["3.png"]
        raw_img = load_image_with_fallback(filenames)
        if raw_img:
            base_img = raw_img.convert_alpha()
            try:
                base_img = pg.transform.smoothscale(
                    base_img, (self.w, self.base_h)
                )
            except Exception:
                base_img = pg.transform.scale(base_img, (self.w, self.base_h))
        else:
            base_img = pg.Surface((self.w, self.h))
            base_img.fill(
                (200, 200, 200) if char_type == "man" else (255, 200, 0)
            )

        if char_type == "man":
            self.img_right = base_img
            self.img_left = pg.transform.flip(base_img, True, False)
        else:
            self.img_left = base_img
            self.img_right = pg.transform.flip(base_img, True, False)

    def update(self, shift_pressed: bool) -> None:
        """キー入力に応じて移動・ジャンプ・しゃがみ状態を更新する"""
        if self.speed_timer > 0:
            self.speed_timer -= 1
        if self.small_timer > 0:
            self.small_timer -= 1

        keys = pg.key.get_pressed()
        spd = self.boost_speed if shift_pressed else self.normal_speed
        if self.speed_timer > 0:
            spd += 5.0

        # 左右移動
        if keys[pg.K_a] or keys[pg.K_LEFT]:
            self.x -= spd
            self.facing_right = False
        if keys[pg.K_d] or keys[pg.K_RIGHT]:
            self.x += spd
            self.facing_right = True

        # 縮小アイテムに応じた基準サイズ計算
        scale = 0.6 if self.small_timer > 0 else 1.0
        self.w = int(65 * scale)
        current_base_h = int(self.base_h * scale)

        # しゃがみ処理 (Sキー / ↓キー)
        if (keys[pg.K_s] or keys[pg.K_DOWN]) and not self.is_jumping:
            self.is_crouching = True
            self.h = int(current_base_h * 0.5)
        else:
            self.is_crouching = False
            self.h = current_base_h

        # 地面基準Y座標（足元の位置を揃える）
        ground_y = self.base_y + self.base_h
        if not self.is_jumping:
            self.y = ground_y - self.h

        # ジャンプ開始 (Wキー / ↑キー / Spaceキー)
        if (
            (keys[pg.K_w] or keys[pg.K_UP] or keys[pg.K_SPACE])
            and not self.is_jumping
            and not self.is_crouching
        ):
            self.is_jumping = True
            self.vy = self.jump_power

        # ジャンプ物理処理
        if self.is_jumping:
            self.y += self.vy
            self.vy += self.gravity
            if self.y + self.h >= ground_y:
                self.y = ground_y - self.h
                self.is_jumping = False
                self.vy = 0.0

        self.x = max(0, min(self.x, WIDTH - self.w))
        self.rect = pg.Rect(self.x, self.y, self.w, self.h)

    def draw(self, target_surf: pg.Surface) -> None:
        """プレイヤー描画"""
        img = self.img_right if self.facing_right else self.img_left
        if (self.w, self.h) != (65, self.base_h):
            scaled_img = pg.transform.scale(img, (self.w, self.h))
            target_surf.blit(scaled_img, self.rect)
        else:
            target_surf.blit(img, self.rect)
# ----------------------------------------------------
# 杭打ち機の壁クラス
# ----------------------------------------------------
class HammerWall:
    """色ごとに異なる回避方法を迫る壁クラス"""

    def __init__(self, base_speed: float) -> None:
        self.h: int = 165
        self.y: float = -self.h
        self.gap_w: int = 135
        self.gap_x: int = random.randint(80, WIDTH - 80 - self.gap_w)
        self.base_down_speed: float = base_speed
        self.down_speed: float = base_speed
        self.rise_speed: float = 12.0

        self.wall_type: str = random.choice(["normal", "crouch", "jump"])
        self.dodged: bool = False

        # ステート制御
        self.state = "warning"
        self.warning_speed = 3.2  # 上から顔を出すスピードを素早く（0.6 → 3.2）
        self.warning_target_y = 15
        self.hold_timer = 25  # 「ごごごご…」のタメ時間はそのままキープ
        self.ground_hold_timer = 20
        self.timer: int = 0

        self.update_rects()

    def update_rects(self) -> None:
        """壁のタイプに応じたRectサイズの設定"""
        if self.wall_type == "normal":
            self.left_rect = pg.Rect(0, self.y, self.gap_x, self.h)
            self.right_rect = pg.Rect(
                self.gap_x + self.gap_w,
                self.y,
                WIDTH - (self.gap_x + self.gap_w),
                self.h,
            )
        elif self.wall_type == "crouch":
            self.left_rect = pg.Rect(0, self.y, WIDTH, 120)
            self.right_rect = pg.Rect(0, 0, 0, 0)
        elif self.wall_type == "jump":
            self.left_rect = pg.Rect(0, self.y, WIDTH, 60)
            self.right_rect = pg.Rect(0, 0, 0, 0)

    def update(self) -> bool:
        """壁の落下・上昇アニメーション更新"""
        passed: bool = False

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

            if self.wall_type == "crouch":
                land_y = HEIGHT - 220
            elif self.wall_type == "jump":
                land_y = HEIGHT - 115
            else:
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
                self.wall_type = random.choice(["normal", "crouch", "jump"])
                self.gap_x = random.randint(80, WIDTH - 80 - self.gap_w)
                self.dodged = False

        self.update_rects()
        return passed

    def draw(self, target_surf: pg.Surface) -> None:
        """壁の描画"""
        if self.wall_type == "crouch":
            wall_color = (200, 60, 60)
            line_color = (255, 120, 120)
        elif self.wall_type == "jump":
            wall_color = (60, 100, 220)
            line_color = (120, 180, 255)
        else:
            wall_color = (80, 85, 100)
            line_color = (
                (255, 200, 0)
                if self.state in ["warning", "hold"]
                else (220, 60, 60)
            )

        top_wall_height = max(0, int(self.y))
        if top_wall_height > 0 and self.wall_type == "normal":
            pg.draw.rect(
                target_surf, wall_color, (0, 0, WIDTH, top_wall_height)
            )

        if self.y + self.h > 0:
            pg.draw.rect(target_surf, wall_color, self.left_rect)
            if self.wall_type == "normal":
                pg.draw.rect(target_surf, wall_color, self.right_rect)
                pg.draw.rect(
                    target_surf,
                    line_color,
                    (0, self.left_rect.bottom - 8, self.gap_x, 8),
                )
                pg.draw.rect(
                    target_surf,
                    line_color,
                    (
                        self.gap_x + self.gap_w,
                        self.right_rect.bottom - 8,
                        WIDTH - (self.gap_x + self.gap_w),
                        8,
                    ),
                )
            else:
                pg.draw.rect(
                    target_surf,
                    line_color,
                    (0, self.left_rect.bottom - 8, WIDTH, 8),
                )

    def collide(self, player: Player) -> bool:
        """衝突判定"""
        if self.dodged:
            return False

        if self.wall_type == "crouch":
            if self.left_rect.colliderect(player.rect):
                if player.is_crouching:
                    self.dodged = True
                    return False
                return True

        elif self.wall_type == "jump":
            if self.left_rect.colliderect(player.rect):
                if player.is_jumping:
                    self.dodged = True
                    return False
                return True

        else:
            hitbox = player.rect.inflate(-8, -8)
            return self.left_rect.colliderect(
                hitbox
            ) or self.right_rect.colliderect(hitbox)

        return False


#アイテムシステム
class Item:
    def __init__(self):
        self.size = 30  # アイテムの大きさ
        self.x = random.randint(50, WIDTH - 50)   # 画面上部のランダムな位置に生成
        self.y = -30
        self.speed = 4   # 落下速度
        self.kind = random.choice(
            ["hp", "invincible", "speed", "small"]
        )
        img_files = {
            "hp": "hp.png",
            "invincible": "invincible.png",
            "speed": "speed.png",
            "small": "small.png"
        }

        raw_img = load_image_with_fallback(
            [img_files[self.kind]]
        )

        if raw_img:
            self.image = pg.transform.scale(
                raw_img.convert_alpha(),
                (self.size, self.size)
            )
        else:
            self.image = None
        # アイテムの種類をランダムに決定
        # hp:体力回復
        # invincible:無敵
        # speed:移動速度上昇
        # small:こうかとん縮小
        self.rect = pg.Rect(
            self.x,
            self.y,
            self.size,
            self.size
        )
    def update(self):
        self.y += self.speed
        self.rect.y = self.y
    
    def draw(self, surf):
        if self.image:
            surf.blit(
                self.image,
                self.rect
            )

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
    # 効果音・BGMの読み込み（安全処理）
    impact_se = load_sound_safe("impact.mp3", 0.7)
    score_se = load_sound_safe("score.mp3", 0.4)
    dash_se = load_sound_safe("dash.mp3", 1.0)
    play_bgm_safe("bgm.mp3", 0.3)

    raw_bg = load_image_with_fallback(
        ["pg_bg.jpg", "background.jpg", "background.png"]
    )
    bg_img = (
        pg.transform.smoothscale(raw_bg.convert(), (WIDTH, HEIGHT))
        if raw_bg
        else None
    )

    font = pg.font.SysFont(
        ["meiryo", "hiraginosans", "yu gothic", "msgothic"], 36
    )
    font_large = pg.font.SysFont(
        ["meiryo", "hiraginosans", "yu gothic", "msgothic"], 50
    )

    score = 0
    state = "TITLE"
    char_types = ["koukaton", "man"]
    selected_char_idx = 0

    player = Player(char_types[selected_char_idx])
    wall = HammerWall(base_speed=15.0)
    hp_manager = HpManager(max_hp=100, damage=40, invincible_frame=60)
    prev_state = wall.state
    items = []
    item_timer = 0

    canvas = pg.Surface((WIDTH, HEIGHT))
    big_shake_timer = 0

    while True:
        clock.tick(FPS)
        shift_pressed = (
            pg.key.get_pressed()[pg.K_LSHIFT]
            or pg.key.get_pressed()[pg.K_RSHIFT]
        )

        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()

            if event.type == pg.KEYDOWN:
                # ダッシュ音（Shiftキー）
                if event.key in (pg.K_LSHIFT, pg.K_RSHIFT):
                    if dash_se:
                        dash_se.play()

                if state == "TITLE":
                    # 矢印キー・A/Dでキャラ切り替え
                    if event.key in (pg.K_LEFT, pg.K_RIGHT, pg.K_a, pg.K_d):
                        selected_char_idx = (selected_char_idx + 1) % len(
                            char_types
                        )
                        player = Player(char_types[selected_char_idx])
                    elif event.key == pg.K_SPACE:
                        state = "GAME"
                        player = Player(char_types[selected_char_idx])
                        wall = HammerWall(base_speed=15.0)
                        hp_manager = HpManager(
                            max_hp=100, damage=40, invincible_frame=60
                        )
                        score = 0
                        items.clear()
                        item_timer = 0
                        prev_state = wall.state
                        play_bgm_safe("bgm.mp3", 0.3)

                elif state == "GAMEOVER" and event.key == pg.K_SPACE:
                    state = "TITLE"
                    player = Player(char_types[selected_char_idx])
                    play_bgm_safe("bgm.mp3", 0.3)

        draw_background(canvas, bg_img)

        # 1. スタート画面
        if state == "TITLE":
            t_surf = font_large.render(
                "こうかとん回避ゲーム", True, (0, 200, 200)
            )
            s_surf = font.render(
                "◀ 矢印キーでキャラ選択 ▶  /  SPACE START",
                True,
                (255, 0, 0),
            )
            canvas.blit(t_surf, t_surf.get_rect(center=(WIDTH // 2, 200)))
            canvas.blit(s_surf, s_surf.get_rect(center=(WIDTH // 2, 280)))
            player.draw(canvas)

        # 2. プレイ画面
        elif state == "GAME":
            player.update(shift_pressed)
            hp_manager.update()
            item_timer += 1

            if item_timer >= 300:
                items.append(Item())
                item_timer = 0

            # アイテムの移動と取得判定
            for item in items[:]:
                item.update()
                if item.rect.colliderect(player.rect):
                    if item.kind == "hp":
                        hp_manager.heal(20)
                    elif item.kind == "invincible":
                        hp_manager.invincible_timer = 180
                    elif item.kind == "speed":
                        player.speed_timer = 300
                    elif item.kind == "small":
                        player.small_timer = 300
                    items.remove(item)
                elif item.y > HEIGHT:
                    items.remove(item)

            if wall.update():
                score += 1
                wall.base_down_speed = 15.0 + score * 0.5
                big_shake_timer = 10
                if score_se:
                    score_se.play()

            # 壁が落下し始めた瞬間のインパクト音
            if wall.state == "falling" and prev_state != "falling":
                if impact_se:
                    impact_se.play()

            prev_state = wall.state

            # 衝突判定・HP処理
            if wall.collide(player):
                if hp_manager.take_damage():
                    if hp_manager.is_dead():
                        state = "GAMEOVER"
                        pg.mixer.music.stop()
                    elif wall.wall_type == "normal":
                        # 生き残っている場合は壁の隙間の中央へ退避させて連続ダメージを防ぐ
                        safe_center = wall.gap_x + wall.gap_w / 2
                        player.x = safe_center - player.w / 2
                        player.x = max(0, min(player.x, WIDTH - player.w))
                        player.rect.x = player.x

            wall.draw(canvas)
            for item in items:
                item.draw(canvas)
            player.draw(canvas)

            text_color = (30, 30, 30) if bg_img else (255, 255, 255)
            score_surf = font.render(f"Score: {score}", True, text_color)
            canvas.blit(score_surf, (20, 20))

            # HPバー描画
            hp_manager.draw(canvas, font, text_color)

            # 被弾時の赤フラッシュエフェクト
            if hp_manager.hit_flash_timer > 0:
                overlay = pg.Surface((WIDTH, HEIGHT))
                overlay.fill((255, 0, 0))
                overlay.set_alpha(60)
                canvas.blit(overlay, (0, 0))

        # 3. ゲームオーバー画面
        elif state == "GAMEOVER":
            go_surf = font_large.render("しんだ", True, (255, 50, 50))
            sc_surf = font.render(f"Score: {score}", True, (255, 255, 255))
            rt_surf = font.render(
                "SPACEでタイトルに戻る", True, (255, 0, 0)
            )

            canvas.blit(go_surf, go_surf.get_rect(center=(WIDTH // 2, 220)))
            canvas.blit(sc_surf, sc_surf.get_rect(center=(WIDTH // 2, 300)))
            canvas.blit(rt_surf, rt_surf.get_rect(center=(WIDTH // 2, 370)))

        # ---------------- 画面振動 ----------------
        offset_x, offset_y = 0, 0
        if state == "GAME":
            if wall.state == "warning":
                offset_x, offset_y = random.randint(-2, 2), random.randint(
                    -2, 2
                )
            elif wall.state == "hold":
                offset_x, offset_y = random.randint(-10, 10), random.randint(
                    -10, 10
                )
            elif big_shake_timer > 0:
                big_shake_timer -= 1
                offset_x, offset_y = random.randint(-8, 8), random.randint(
                    -8, 8
                )

        screen.fill((0, 0, 0))
        screen.blit(canvas, (offset_x, offset_y))
        pg.display.flip()


if __name__ == "__main__":
    main()

