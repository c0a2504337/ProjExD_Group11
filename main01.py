import os
import random
import sys
import pygame as pg

# スクリプトの保存先フォルダをカレントディレクトリに変更
os.chdir(os.path.dirname(os.path.abspath(__file__)))
WIDTH = 1100
HEIGHT = 650
FPS = 60

# ↓追記部分
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # ファイルの基準ディレクトリを取得
os.chdir(BASE_DIR)  # カレントディレクトリの変更（必須記述）
# ↑追記部分

pg.init()
pg.mixer.init()  # ← 【重要】サウンド機能を初期化

screen = pg.display.set_mode((WIDTH, HEIGHT))
pg.display.set_caption("逃げろ工科トン")
clock = pg.time.Clock()

# ==================== 【追加】BGM・効果音の読み込みと設定 ====================
pg.mixer.music.load("sound/bgm.mp3")
pg.mixer.music.play(-1)  # BGMループ再生
pg.mixer.music.set_volume(0.3)

impact_se = pg.mixer.Sound("sound/impact.mp3")
impact_se.set_volume(0.7)

score_se = pg.mixer.Sound("sound/score.mp3")
score_se.set_volume(0.4)

dash_se = pg.mixer.Sound("sound/dash.mp3")
dash_se.set_volume(1.0)
# ===========================================================================


def load_image_with_fallback(filenames):
    """実行環境に合わせて画像を探索"""
    for fname in filenames:
        candidates = [os.path.join("fig", fname), fname]
        # ↓追記部分
        candidates = [
            os.path.join(BASE_DIR, "fig", fname),  # 絶対パス指定で画像の探索精度向上
            os.path.join(BASE_DIR, fname),
            fname
        ]
        # ↑追記部分
        for path in candidates:
            if os.path.exists(path):
                try:
                    return pg.image.load(path)
                except Exception:
                    pass
    return None

# HP管理クラス（追加：審査用、HP/無敵時間/描画をまとめる）

class HpManager:
    
    def __init__(self, max_hp:int, damage:int, invincible_frame:int) -> None:
        """HP管理の初期化"""    
        self.max_hp = max_hp
        self.hp = max_hp
        self.damage = damage
        self.invincible_frame = invincible_frame
        self.invincible_timer = 0
        self.hit_flash_timer = 0

    def update(self) -> None:
        """無敵時間の更新処理"""   
        if self.invincible_timer > 0:
            self.invincible_timer -= 1
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -=1                                                                                                             
    def take_damage(self) -> None:
        """ダメージを受ける処理"""   
        if self.invincible_timer <= 0:
            self.hp -= self.damage
            self.invincible_timer = self.invincible_frame
            self.hit_flash_timer = 12  
            if self.hp < 0:
                self.hp = 0

    def is_dead(self) -> int:
        """死亡判定を返す"""   
        return self.hp <= 0
    
    def draw(self, target_surf: pg.Surface, font:pg.font, text_color:tuple) -> None:
        # 描画処理
        """HPバー描画"""
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
        pg.draw.rect(target_surf, hp_color, (bar_x, bar_y, bar_w * hp_ratio, bar_h))
        pg.draw.rect(target_surf, (255,255,255), (bar_x, bar_y, bar_w, bar_h), 2)
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
        # ↓追記部分
        self.base_h: int = 65                # 通常時の高さを保持（しゃがみ解除用）
        self.h: int = self.base_h
        self.x: float = WIDTH // 2 - self.w // 2
        self.base_y: float = HEIGHT - 115    # 地上の初期Y座標を保持（着地用）
        self.y: float = self.base_y
        # ↑追記部分
        self.normal_speed: float = 7.5
        self.boost_speed: float = 14.0

        # ↓追記部分
        # ジャンプ・しゃがみ用パラメータ
        self.is_jumping: bool = False        # ジャンプ中かどうか
        self.jump_power: float = -20.0       # ジャンプした瞬間の上方向への速度
        self.gravity: float = 1.2            # 毎フレームかかる重力加速度
        self.vy: float = 0.0                 # 現在のY軸方向の速度

        self.is_crouching: bool = False      # しゃがみ中かどうか
        # ↑追記部分

        self.rect: pg.Rect = pg.Rect(self.x, self.y, self.w, self.h)
        self.facing_right: bool = True

        filenames = ["man.png"] if char_type == "man" else ["3.png"]
        raw_img = load_image_with_fallback(filenames)
        if raw_img:
            base_img = raw_img.convert_alpha()
            try:
                base_img = pg.transform.smoothscale(base_img, (self.w, self.base_h))
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
        keys = pg.key.get_pressed()
        spd = self.boost_speed if shift_pressed else self.normal_speed

        # 左右移動
        if keys[pg.K_a] or keys[pg.K_LEFT]:
            self.x -= spd
            self.facing_right = False
        if keys[pg.K_d] or keys[pg.K_RIGHT]:
            self.x += spd
            self.facing_right = True
        self.x = max(0, min(self.x, WIDTH - self.w))

        # ↓追記部分
        # しゃがみ処理 (Sキー / ↓キー)
        if (keys[pg.K_s] or keys[pg.K_DOWN]) and not self.is_jumping:
            self.is_crouching = True
            self.h = 30                      # 身長を小さくする
            self.y = self.base_y + (self.base_h - self.h)  # 足元が浮かないようY座標を下方に調整
        else:
            self.is_crouching = False
            self.h = self.base_h
            if not self.is_jumping:
                self.y = self.base_y

        # ジャンプ開始 (Wキー / ↑キー / Spaceキー)
        if (keys[pg.K_w] or keys[pg.K_UP] or keys[pg.K_SPACE]) and not self.is_jumping and not self.is_crouching:
            self.is_jumping = True
            self.vy = self.jump_power        # 上方向の速度を設定

        # ジャンプ物理処理
        if self.is_jumping:
            self.y += self.vy
            self.vy += self.gravity          # 重力で下降速度を加速
            if self.y >= self.base_y:        # 地面に達したら着地
                self.y = self.base_y
                self.is_jumping = False
                self.vy = 0.0
        # ↑追記部分

        self.rect = pg.Rect(self.x, self.y, self.w, self.h)
    def draw(self, target_surf: pg.Surface) -> None:
        """プレイヤー描画"""
        img = self.img_right if self.facing_right else self.img_left
        # ↓追記部分
        if self.is_crouching:
            scaled_img = pg.transform.scale(img, (self.w, self.h))  # しゃがみ用に縦幅を縮小して描画
            target_surf.blit(scaled_img, self.rect)
        else:
            target_surf.blit(img, self.rect)
        # ↑追記部分


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

        # ↓追記部分
        self.wall_type: str = random.choice(["normal", "crouch", "jump"])  # 壁の種類（通常/しゃがみ回避/ジャンプ回避）をランダムに設定
        self.dodged: bool = False            # 今回の壁の回避に成功したかどうかのフラグ
        # ↑追記部分

        self.state: str = "warning"
        self.warning_speed: float = 3.2
        self.warning_target_y: float = 15.0
        self.hold_timer: int = 25
        self.ground_hold_timer: int = 20

        self.update_rects()

    def update_rects(self) -> None:
        """壁のタイプに応じたRectサイズの設定"""
        # ↓追記部分
        if self.wall_type == "normal":
            self.left_rect = pg.Rect(0, self.y, self.gap_x, self.h)
            self.right_rect = pg.Rect(self.gap_x + self.gap_w, self.y, WIDTH - (self.gap_x + self.gap_w), self.h)
        elif self.wall_type == "crouch":
            self.left_rect = pg.Rect(0, self.y, WIDTH, 120)       # 画面全体を覆う高い壁
            self.right_rect = pg.Rect(0, 0, 0, 0)
        elif self.wall_type == "jump":
            self.left_rect = pg.Rect(0, self.y, WIDTH, 60)        # 画面全体を覆う低い壁
            self.right_rect = pg.Rect(0, 0, 0, 0)
        # ↑追記部分

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

            # ↓追記部分
            # 壁の種類ごとに止まる高さ（足元の隙間）を変更
            if self.wall_type == "crouch":
                land_y = HEIGHT - 220         # 隙間を50pxにし、しゃがみ(30px)でのみ通れるように調整（棒立ち65pxは激突）
            elif self.wall_type == "jump":
                land_y = HEIGHT - 115         # ジャンプで飛び越える高さで停止
            else:
                land_y = HEIGHT - self.h
            # ↑追記部分

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
                # ↓追記部分
                self.wall_type = random.choice(["normal", "crouch", "jump"])  # 次に降ってくる壁の種類を選び直す
                self.gap_x = random.randint(80, WIDTH - 80 - self.gap_w)
                self.dodged = False           # 次の壁用に回避フラグをリセット
                # ↑追記部分

        self.update_rects()
        return passed

    def draw(self, target_surf: pg.Surface) -> None:
        """壁の描画"""
        # ↓追記部分
        # 壁のタイプごとに配色を変更
        if self.wall_type == "crouch":
            wall_color = (200, 60, 60)        # 赤色（しゃがみ回避）
            line_color = (255, 120, 120)
        elif self.wall_type == "jump":
            wall_color = (60, 100, 220)       # 青色（ジャンプ回避）
            line_color = (120, 180, 255)
        else:
            wall_color = (80, 85, 100)        # グレー（隙間移動回避）
            line_color = (255, 200, 0) if self.state in ["warning", "hold"] else (220, 60, 60)
        # ↑追記部分

        top_wall_height = max(0, int(self.y))
        if top_wall_height > 0 and self.wall_type == "normal":
            pg.draw.rect(target_surf, wall_color, (0, 0, WIDTH, top_wall_height))

        if self.y + self.h > 0:
            pg.draw.rect(target_surf, wall_color, self.left_rect)
            if self.wall_type == "normal":
                pg.draw.rect(target_surf, wall_color, self.right_rect)
                pg.draw.rect(target_surf, line_color, (0, self.left_rect.bottom - 8, self.gap_x, 8))
                pg.draw.rect(target_surf, line_color, (self.gap_x + self.gap_w, self.right_rect.bottom - 8, WIDTH - (self.gap_x + self.gap_w), 8))
            else:
                # ↓追記部分
                pg.draw.rect(target_surf, line_color, (0, self.left_rect.bottom - 8, WIDTH, 8))  # 全幅の警告ラインを描画
                # ↑追記部分

    # ↓追記部分
    def collide(self, player: Player) -> bool:
        """衝突判定
        
        - 実際に壁がプレイヤーに接触したタイミングで回避判定を行う
        - 壁に触れる前のフライング（先行ジャンプ/しゃがみ）では無敵フラグが立たないよう改善
        """
        if self.dodged:
            return False                      # すでに回避成功していれば当たり判定をスルー

        if self.wall_type == "crouch":
            if self.left_rect.colliderect(player.rect):
                if player.is_crouching:
                    self.dodged = True        # 接触した瞬間にしゃがんでいれば回避成功
                    return False
                return True                   # しゃがんでいなければ激突

        elif self.wall_type == "jump":
            if self.left_rect.colliderect(player.rect):
                if player.is_jumping:
                    self.dodged = True        # 接触した瞬間にジャンプしていれば回避成功
                    return False
                return True                   # ジャンプしていなければ激突

        else:
            hitbox = player.rect.inflate(-8, -8)  # 通常壁のすれ違い判定調整
            return self.left_rect.colliderect(hitbox) or self.right_rect.colliderect(hitbox)

        return False
    # ↑追記部分


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
    score = 0
    state = "TITLE"
    char_types = ["koukaton", "man"]
    selected_char_idx = 0

    player = Player(char_types[selected_char_idx])
    wall = HammerWall(base_speed=15.0)
    score = 0
    game_over = False
    # HPはクラスで管理
    hp_manager = HpManager(max_hp=100, damage=20, invincible_frame=60)
    canvas = pg.Surface((WIDTH, HEIGHT))
    big_shake_timer = 0

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

    while True:
        clock.tick(FPS)
        shift_pressed = pg.key.get_pressed()[pg.K_LSHIFT] or pg.key.get_pressed()[pg.K_RSHIFT]
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()

        if not game_over:
            player.update(shift_pressed)
            if wall.update():
                score += 1
                wall.base_down_speed = 15.0 + score * 0.5
                big_shake_timer = 10
                score_se.play()  # 【追加】スコアアップ音

            # 【追加】壁が落下し始めた瞬間のインパクト音
            if wall.state == "falling" and prev_state != "falling":
                impact_se.play()

            prev_state = wall.state

            # ↓追記部分（判定処理にPlayerオブジェクト自体を渡し、stateをGAMEOVERへ切り替え）
            if wall.collide(player):
                state = "GAMEOVER"
                pg.mixer.music.stop()  # ゲームオーバー時にBGM停止
            # ↑追記部分

            wall.draw(canvas)
            player.draw(canvas)

            text_color = (30, 30, 30) if bg_img else (255, 255, 255)
            score_surf = font.render(f"Score: {score}", True, text_color)
            canvas.blit(score_surf, (20, 20))

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

            hp_manager.update()
            # 衝突判定
            if wall.collide(player.rect):
                hp_manager.take_damage()
            # 受击時、隙間へ強制移動、壁に挟まらないようにする
                safe_center = wall.gap_x + wall.gap_w / 2
                player.x = safe_center - player.w / 2
                player.x = max(0, min(player.x, WIDTH - player.w))
                player.rect.x = player.x
                if hp_manager.is_dead():
                    game_over = True
        draw_background(canvas, bg_img)
        wall.draw(canvas)
        player.draw(canvas)
        text_color = (30, 30, 30) if bg_img else (255, 255, 255)
        score_surf = font.render(f"Score: {score}", True, text_color)
        canvas.blit(score_surf, (20, 20))
        # HP描画呼び出し
        hp_manager.draw(canvas, font, text_color)
        # 被弾時の赤フラッシュエフェクト
        if hp_manager.hit_flash_timer > 0:
            overlay = pg.Surface((WIDTH, HEIGHT))
            overlay.fill((255,0,0))
            overlay.set_alpha(60)
            canvas.blit(overlay,(0,0))
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
