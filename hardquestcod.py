import arcade
import random
import math
import time
import os
from PIL import Image

SCREEN_TITLE = "Hard Quest"

# Размер одного квадратного блока земли
BLOCK_SIZE = 128

# --- ПАРАМЕТРЫ ИГРОКА ---
PLAYER_START_HP = 100
PLAYER_DAMAGE = 55
PLAYER_SPEED = 9
PLAYER_JUMP_SPEED = 30
GRAVITY = 1.3
# Сколько секунд игрок будет неуязвим после того, как его ударили
INVULNERABILITY_TIME = 1.0

# --- ПАРАМЕТРЫ БОЯ ---
# Как далеко достает меч
ATTACK_RANGE = 240
# Сколько времени (в секундах) отображается картинка атаки
ATTACK_DURATION = 0.5

# --- ПАРАМЕТРЫ ВРАГОВ (ОБЫЧНЫЕ) ---
ENEMY_DAMAGE = 15
ENEMY_SPEED = 3.5

# --- ПАРАМЕТРЫ ПРИЗРАКОВ ---
GHOST_HP = 80
GHOST_SPEED = 3.0
# Пауза между выстрелами (в секундах)
GHOST_SHOOT_DELAY = 7.0
PROJECTILE_SPEED = 7
PROJECTILE_DAMAGE = 8
# Насколько сильно снаряды падают вниз под действием гравитации
PROJECTILE_GRAVITY = 0.08

# --- ПАРАМЕТРЫ БОССА (СДЕЛАЛИ ЕЩЕ СЛАБЕЕ) ---
BOSS_HP = 1300
BOSS_NORMAL_SPEED = 2.5
BOSS_DASH_SPEED = 8.5
# Урон снаряда босса
BOSS_PROJECTILE_DAMAGE = 5
# Урон от касания самого босса
BOSS_COLLISION_DAMAGE = 8

# --- СОСТОЯНИЯ ИГРЫ (ЭКРАНЫ) ---
STATE_MENU = 0
STATE_COUNTDOWN = 1
STATE_GAME = 2
STATE_GAME_OVER = 3
STATE_WIN = 4
STATE_PAUSE = 5

# ==============================================================================
# 2. ФУНКЦИИ ДЛЯ РАБОТЫ С КАРТИНКАМИ
# ==============================================================================

def prepare_texture(filename, mirror=False, should_clean_bg=True):
    """
    Эта функция готовит наши картинки (спрайты) к использованию.
    Она умеет убирать белый фон и разворачивать персонажей в нужную сторону.
    """

    # Если файла почему-то нет - не вылетаем, а рисуем серый квадрат
    if not os.path.exists(filename):
        print(f"Ошибка: не найден файл {filename}")
        return arcade.make_soft_square_texture(64, arcade.color.GRAY)

    # Если нам не нужно чистить фон (например, для неба), грузим сразу
    if should_clean_bg == False:
        return arcade.load_texture(filename)

    try:
        # Открываем изображение через библиотеку PIL
        raw_image = Image.open(filename).convert("RGBA")

        # Загружаем пиксели для обработки
        pixels = raw_image.load()
        shirina, visota = raw_image.size

        # Перебираем каждый пиксель по горизонтали и вертикали
        for y in range(visota):
            for x in range(shirina):
                # r, g, b - это цвета, a - прозрачность
                r, g, b, a = pixels[x, y]

                # Если пиксель очень светлый (почти белый), делаем его прозрачным
                if r > 235 and g > 230 and b > 230:
                    pixels[x, y] = (255, 255, 255, 0)

        # Находим границы рисунка, чтобы отрезать пустые места по краям
        image_box = raw_image.getbbox()
        if image_box:
            raw_image = raw_image.crop(image_box)

        # Если персонаж должен смотреть влево - переворачиваем картинку
        if mirror == True:
            raw_image = raw_image.transpose(Image.FLIP_LEFT_RIGHT)

        # Превращаем картинку PIL в текстуру для игрового движка
        final_texture = arcade.Texture(raw_image)
        return final_texture

    except Exception as e:
        print(f"Не удалось обработать картинку {filename}: {e}")
        return arcade.make_soft_square_texture(64, arcade.color.GRAY)

# ==============================================================================
# 3. КЛАССЫ ПЕРСОНАЖЕЙ И ПРЕДМЕТОВ
# ==============================================================================

class GhostEnemy(arcade.Sprite):
    """
    Голубой призрак. Он умеет летать и стрелять в игрока.
    """
    def __init__(self, texture, scale):
        super().__init__(texture, scale)
        self.hp = GHOST_HP
        # Добавляем случайную задержку перед первым выстрелом
        pauza = random.uniform(0, 5)
        self.last_shoot_time = time.time() + pauza

class BossEnemy(arcade.Sprite):
    """
    Финальный босс. У него две фазы: спокойная и рывок (dash).
    """
    def __init__(self, texture, scale):
        super().__init__(texture, scale)
        self.hp = BOSS_HP
        # Начальное состояние
        self.state = "normal"
        # Таймеры для переключения фаз и стрельбы
        self.state_timer = 0
        self.shoot_timer = 0

class Bullet(arcade.Sprite):
    """
    Снаряд, который летит в сторону игрока.
    """
    def __init__(self, texture, scale, dx, dy, damage_amount=8):
        super().__init__(texture, scale)

        # Скорость полета
        self.change_x = dx
        self.change_y = dy

        # Урон снаряда
        self.damage = damage_amount

    def update(self):
        """
        Каждый кадр снаряд падает чуть-чуть вниз из-за гравитации.
        """
        self.change_y = self.change_y - PROJECTILE_GRAVITY

        # Обновляем координаты
        self.center_x = self.center_x + self.change_x
        self.center_y = self.center_y + self.change_y

# ==============================================================================
# 4. ГЛАВНЫЙ КЛАСС ИГРЫ (ОКНО И ЛОГИКА)
# ==============================================================================

class MyGame(arcade.Window):
    def __init__(self):
        # Создаем окно игры на весь экран
        super().__init__(title=SCREEN_TITLE, fullscreen=True)

        # Запоминаем размеры окна
        self.screen_width, self.screen_height = self.get_size()

        # Стартовое состояние - меню
        self.game_state = STATE_MENU
        self.current_level = 1
        self.player_hp = PLAYER_START_HP

        # Переменные времени и направления
        self.last_hit_time = 0
        self.last_attack_time = 0
        self.is_facing_right = True
        self.countdown_value = 3.0
        self.total_time = 0.0

        # Инициализируем объекты сцены и физики как "Пусто"
        self.scene = None
        self.player_sprite = None
        self.physics_engine = None

        # Камеры
        self.camera = None
        self.gui_camera = None

        # Словари для хранения ресурсов
        self.textures = {}
        self.scales = {}

        # Плеер для фоновой музыки
        self.music_player = None

        # Список путей к файлам (картинки)
        self.files = {
            "player": "assets/images/player_idle.jpg",
            "player_attack": "assets/images/player_attack.png",
            "ground": "assets/images/grassMid.png",
            "platform": "assets/images/grassHalfMid.png",
            "enemy": "assets/images/enemyFloating_1.png",
            "ghost": "assets/images/ghost.png",
            "projectile": "assets/images/projectile.png",
            "coin": "assets/images/coinGold.jpg",
            "bg": "assets/images/bg_castle.jpg",
            "bush": "assets/images/bush.jpg",
            "boss": "assets/images/boss_new.png",
            "boss_bg": "assets/images/boss_bg.jpg"
        }

    def load_resources(self):
        if self.textures:
            return

        print("Загружаю ресурсы... Пожалуйста, подождите.")

        # --- ТЕКСТУРЫ ГЕРОЯ ---
        self.textures["player_r"] = prepare_texture(self.files["player"], mirror=False)
        self.textures["player_l"] = prepare_texture(self.files["player"], mirror=True)
        self.textures["player_attack_r"] = prepare_texture(self.files["player_attack"], mirror=False)
        self.textures["player_attack_l"] = prepare_texture(self.files["player_attack"], mirror=True)

        # --- ТЕКСТУРЫ МОНСТРОВ ---
        self.textures["enemy"] = prepare_texture(self.files["enemy"])
        self.textures["ghost"] = prepare_texture(self.files["ghost"])
        self.textures["projectile"] = prepare_texture(self.files["projectile"])
        self.textures["boss"] = prepare_texture(self.files["boss"])

        # --- ТЕКСТУРЫ ОКРУЖЕНИЯ ---
        # Фоны грузим БЕЗ очистки пикселей, чтобы не было "дырок" в небе
        self.textures["bg_1"] = prepare_texture(self.files["bg"], should_clean_bg=False)
        self.textures["bg_boss"] = prepare_texture(self.files["boss_bg"], should_clean_bg=False)
        self.textures["ground"] = prepare_texture(self.files["ground"], should_clean_bg=False)
        self.textures["platform"] = prepare_texture(self.files["platform"], should_clean_bg=False)
        self.textures["bush"] = prepare_texture(self.files["bush"])
        self.textures["coin"] = prepare_texture(self.files["coin"], should_clean_bg=False)

        # --- РАСЧЕТ МАСШТАБОВ ---
        # Подгоняем размеры картинок под наши игровые стандарты (128 пикселей блок)

        s_blok = self.textures["ground"].width
        if s_blok == 0: s_blok = 128
        self.scales["tile"] = BLOCK_SIZE / s_blok

        v_igrok = self.textures["player_r"].height
        self.scales["player"] = (BLOCK_SIZE * 1.2) / v_igrok

        v_vrag = self.textures["enemy"].height
        self.scales["enemy"] = (BLOCK_SIZE * 0.9) / v_vrag

        v_ghost = self.textures["ghost"].height
        self.scales["ghost"] = (BLOCK_SIZE * 1.8) / v_ghost

        v_boss = self.textures["boss"].height
        self.scales["boss"] = (BLOCK_SIZE * 4.5) / v_boss

        # --- ЗВУКИ И МУЗЫКА ---
        try:
            self.sound_jump = arcade.load_sound(":resources:sounds/jump1.wav")
            self.sound_hit = arcade.load_sound(":resources:sounds/hit3.wav")
            self.sound_attack = arcade.load_sound(":resources:sounds/fall3.wav")

            if os.path.exists("assets/music.mp3"):
                self.bg_music = arcade.load_sound("assets/music.mp3")
            if os.path.exists("726ae3d59a7576a.mp3"):
                self.boss_music = arcade.load_sound("726ae3d59a7576a.mp3")
        except Exception as err:
            print(f"Предупреждение: не удалось загрузить аудио. {err}")

    def setup(self, level_number):
        """
        Создает мир уровня: землю, платформы, врагов и игрока.
        """
        self.current_level = level_number

        # Создаем камеры
        self.camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()

        # Создаем пустую сцену
        self.scene = arcade.Scene()

        # Подготавливаем списки спрайтов для разных слоев
        sloi = ["Background", "Walls", "Decorations", "Enemies", "Ghosts", "Projectiles", "Boss", "Portal", "Player"]
        for imya_sloya in sloi:
            self.scene.add_sprite_list(imya_sloya)

        # Загружаем ресурсы
        self.load_resources()

        # Сброс HP и таймеров
        if level_number == 1:
            self.player_hp = PLAYER_START_HP
            self.total_time = 0.0

        # --- НАСТРОЙКА МУЗЫКИ ---
        if self.music_player:
            arcade.stop_sound(self.music_player)

        # Выбираем мелодию
        if level_number == 1:
            muzon = self.bg_music
        else:
            muzon = self.boss_music

        if muzon:
            try:
                self.music_player = arcade.play_sound(muzon, loop=True, volume=0.4)
            except:
                pass

        # --- СОЗДАНИЕ ФОНА ---
        if level_number == 1:
            tex_fon = self.textures["bg_1"]
        else:
            tex_fon = self.textures["bg_boss"]

        bg_sprite = arcade.Sprite(tex_fon)

        # Растягиваем фон на весь экран
        mas_visota = self.screen_height / bg_sprite.height
        mas_shirina = self.screen_width / bg_sprite.width
        max_mas = max(mas_visota, mas_shirina) * 1.1

        bg_sprite.scale = max_mas
        bg_sprite.center_x = self.screen_width / 2
        bg_sprite.center_y = self.screen_height / 2

        self.scene.add_sprite("Background", bg_sprite)

        # --- ГЕНЕРАЦИЯ МИРА (ЗЕМЛЯ) ---
        t_scale = self.scales["tile"]

        # Ширина и высота блока на экране
        grid_x = int(self.textures["ground"].width * t_scale) - 1
        grid_y = int(self.textures["ground"].height * t_scale * 0.75)

        if level_number == 1:
            # ПЕРВЫЙ УРОВЕНЬ
            konec_puti = 12000

            # Строим землю (далеко влево и далеко вправо)
            for x in range(-2000, konec_puti + 5000, grid_x):
                for ryad in range(7):
                    kirpich = arcade.Sprite(self.textures["ground"], scale=t_scale)
                    kirpich.center_x = x
                    kirpich.center_y = 250 - (ryad * grid_y)
                    self.scene.add_sprite("Walls", kirpich)

                    # Декорации на поверхности
                    if ryad == 0:
                        if random.random() < 0.18:
                            bush = arcade.Sprite(self.textures["bush"], scale=t_scale * 0.8)
                            bush.center_x = x
                            bush.bottom = kirpich.top
                            self.scene.add_sprite("Decorations", bush)

            # Ставим 70 парящих платформ
            for i in range(70):
                p = arcade.Sprite(self.textures["platform"], scale=t_scale)
                p.center_x = random.randint(500, konec_puti - 500)
                p.center_y = random.randint(450, 1400)
                self.scene.add_sprite("Walls", p)

            # Голубые призраки (4 штуки)
            for i in range(4):
                pr = GhostEnemy(self.textures["ghost"], scale=self.scales["ghost"])
                pr.center_x = random.randint(1500, konec_puti - 1000)
                pr.center_y = random.randint(700, 1500)
                self.scene.add_sprite("Ghosts", pr)

            # Летучие мыши
            for i in range(18):
                bat = arcade.Sprite(self.textures["enemy"], scale=self.scales["enemy"])
                bat.center_x = random.randint(1000, konec_puti - 500)
                bat.center_y = random.randint(500, 1000)
                bat.hp = 40
                self.scene.add_sprite("Enemies", bat)

            # Портал-монета
            portal = arcade.Sprite(self.textures["coin"], scale=t_scale * 2.5)
            portal.position = (konec_puti, 450)
            self.scene.add_sprite("Portal", portal)

            # Позиция игрока
            start_x = 200
            start_y = 450

        else:
            # УРОВЕНЬ БОССА
            granica_leva = -6000
            granica_prava = 6000

            for x in range(granica_leva, granica_prava + 3000, grid_x):
                for ryad in range(7):
                    kirpich = arcade.Sprite(self.textures["ground"], scale=t_scale)
                    kirpich.center_x = x
                    kirpich.center_y = 200 - (ryad * grid_y)
                    # Земля на арене босса темная
                    kirpich.color = (40, 40, 60)
                    self.scene.add_sprite("Walls", kirpich)

                    if ryad == 0:
                        if random.random() < 0.12:
                            bush = arcade.Sprite(self.textures["bush"], scale=t_scale * 0.8)
                            bush.center_x = x
                            bush.bottom = kirpich.top
                            bush.color = (60, 60, 80)
                            self.scene.add_sprite("Decorations", bush)

            # Платформы для боя
            for i in range(30):
                p = arcade.Sprite(self.textures["platform"], scale=t_scale)
                p.center_x = random.randint(-2000, 5000)
                p.center_y = random.randint(400, 1300)
                p.color = (40, 40, 60)
                self.scene.add_sprite("Walls", p)

            # Создаем босса
            boss_obj = BossEnemy(self.textures["boss"], scale=self.scales["boss"])
            boss_obj.center_x = 3000
            boss_obj.bottom = 250
            self.scene.add_sprite("Boss", boss_obj)

            start_x = 200
            start_y = 400

        # --- СОЗДАНИЕ ИГРОКА ---
        self.player_sprite = arcade.Sprite(self.textures["player_r"], scale=self.scales["player"])
        self.player_sprite.position = (start_x, start_y)
        self.scene.add_sprite("Player", self.player_sprite)

        # Настройка физики
        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.player_sprite,
            gravity_constant=GRAVITY,
            walls=self.scene["Walls"]
        )

        # ЗАПУСКАЕМ ИГРУ (ОТСЧЕТ) ПОСЛЕ ВСЕЙ ЗАГРУЗКИ
        self.countdown_value = 3.5
        self.game_state = STATE_COUNTDOWN

    def on_draw(self):
        """
        Метод рисования (вызывается постоянно).
        """
        self.clear() # Чистим экран

        # --- ЭКРАН МЕНЮ ---
        if self.game_state == STATE_MENU:
            self.load_resources()

            # Рисуем фон
            f_menu = arcade.Sprite(self.textures["bg_1"])
            f_menu.scale = max(self.width / f_menu.width, self.height / f_menu.height) * 1.1
            f_menu.center_x = self.width / 2
            f_menu.center_y = self.height / 2

            # Отрисовка фона (фикс ошибки AttributeError)
            s_list = arcade.SpriteList()
            s_list.append(f_menu)
            s_list.draw()

            arcade.draw_text("Hard Quest", self.width/2, self.height/2 + 100,
                             arcade.color.GOLD, 60, anchor_x="center", bold=True)
            arcade.draw_text("Нажмите ENTER, чтобы начать приключение", self.width/2, self.height/2,
                             arcade.color.WHITE, 30, anchor_x="center")
            return

        # --- РИСОВАНИЕ МИРА ---
        self.camera.use()
        self.scene.draw()

        # --- РИСОВАНИЕ ИНТЕРФЕЙСА (HUD) ---
        self.gui_camera.use()

        # Полоска ХП
        arcade.draw_lrbt_rectangle_filled(40, 340, self.height-70, self.height-30, arcade.color.BLACK)

        zhizn = self.player_hp / PLAYER_START_HP
        if zhizn < 0: zhizn = 0
        w_poloska = zhizn * 300

        # Если ХП больше 30% - зеленая, иначе - красная
        cvet = arcade.color.RED
        if zhizn > 0.3: cvet = arcade.color.GREEN

        arcade.draw_lrbt_rectangle_filled(40, 40 + w_poloska, self.height-70, self.height-30, cvet)
        arcade.draw_text(f"HP: {int(self.player_hp)}", 50, self.height-65, arcade.color.WHITE, 18, bold=True)

        # Таймер
        m = int(self.total_time // 60)
        s = int(self.total_time % 60)
        stroka_vremeni = f"TIME: {m:02d}:{s:02d}"
        arcade.draw_text(stroka_vremeni, self.width-250, self.height-65, arcade.color.GOLD, 24, bold=True)

        # ХП БОССА
        if self.current_level == 2:
            if len(self.scene["Boss"]) > 0:
                bossik = self.scene["Boss"][0]
                hp_text = int(bossik.hp)
                if hp_text < 0: hp_text = 0
                arcade.draw_text(f"BOSS HP: {hp_text}", self.width/2, self.height-60,
                                 arcade.color.RED, 35, anchor_x="center", bold=True)

        # --- ЭКРАН ПАУЗЫ ---
        if self.game_state == STATE_PAUSE:
            arcade.draw_lrbt_rectangle_filled(0, self.width, 0, self.height, (0,0,0,120))
            arcade.draw_text("ПАУЗА", self.width/2, self.height/2, arcade.color.WHITE, 80, anchor_x="center", bold=True)
            arcade.draw_text("Нажмите P или ESC, чтобы продолжить", self.width/2, self.height/2 - 60,
                             arcade.color.LIGHT_BLUE, 25, anchor_x="center")

        # --- ОТСЧЕТ ---
        if self.game_state == STATE_COUNTDOWN:
            nomer = int(self.countdown_value)
            if nomer > 0:
                tekst_nomera = str(nomer)
            else:
                tekst_nomera = "GO!"
            arcade.draw_text(tekst_nomera, self.width/2, self.height/2, arcade.color.WHITE, 150, anchor_x="center", bold=True)

        # --- ФИНАЛЬНЫЕ ЭКРАНЫ ---
        if self.game_state == STATE_GAME_OVER:
            arcade.draw_lrbt_rectangle_filled(0, self.width, 0, self.height, (0,0,0,160))
            arcade.draw_text("ГЕРОЙ ПАЛ В БОЮ", self.width/2, self.height/2 + 60, arcade.color.RED, 80, anchor_x="center", bold=True)
            arcade.draw_text("R - Начать заново  |  Q - Выход в меню",
                             self.width/2, self.height/2 - 40, arcade.color.WHITE, 30, anchor_x="center")

        elif self.game_state == STATE_WIN:
            arcade.draw_text("ПОБЕДА!", self.width/2, self.height/2, arcade.color.GOLD, 100, anchor_x="center", bold=True)

    def boss_ai_tick(self, boss, dt):
        """
        Логика того, как думает босс.
        """
        # Считаем расстояние
        dx = self.player_sprite.center_x - boss.center_x
        dy = self.player_sprite.center_y - boss.center_y
        dist = math.sqrt(dx * dx + dy * dy)

        # Обновляем внутренние часы босса
        boss.state_timer = boss.state_timer - dt
        boss.shoot_timer = boss.shoot_timer - dt

        # Решаем, злой босс или нет
        if boss.state == "normal":
            skor = BOSS_NORMAL_SPEED
            boss.color = arcade.color.WHITE
            if boss.state_timer <= 0:
                boss.state = "dash"
                boss.state_timer = 1.5
        else:
            skor = BOSS_DASH_SPEED
            boss.color = (255, 100, 100)
            if boss.state_timer <= 0:
                boss.state = "normal"
                boss.state_timer = 3.0

        # Двигаем босса
        if dist > 0:
            boss.center_x = boss.center_x + (dx / dist) * skor
            boss.center_y = boss.center_y + (dy / dist) * skor

        # Стрельба босса (урон теперь всего 5)
        if boss.shoot_timer <= 0:
            if dist < 1500:
                self.make_projectile(boss, dx, dy, dist, dmg=BOSS_PROJECTILE_DAMAGE, size=0.6)
                boss.shoot_timer = 2.5

    def on_update(self, delta_time):
        """
        Главный цикл обновлений.
        """
        # Если меню, пауза или смерть - ничего не двигаем
        if self.game_state == STATE_MENU: return
        if self.game_state == STATE_PAUSE: return
        if self.game_state == STATE_GAME_OVER: return
        if self.game_state == STATE_WIN: return

        # ИСПРАВЛЕНИЕ: Проверка на существование физики (фикс AttributeError)
        if self.physics_engine is None: return

        # Обработка 3... 2... 1...
        if self.game_state == STATE_COUNTDOWN:
            self.countdown_value = self.countdown_value - delta_time
            if self.countdown_value <= 0.5:
                self.game_state = STATE_GAME

        # Счетчик времени
        if self.game_state == STATE_GAME:
            self.total_time = self.total_time + delta_time

        # Работа физики
        self.physics_engine.update()

        # Двигаем камеру
        self.camera.position = (self.player_sprite.center_x, self.player_sprite.center_y)

        # Фон за камерой
        if len(self.scene["Background"]) > 0:
            f = self.scene["Background"][0]
            f.center_x = self.camera.position.x
            f.center_y = self.camera.position.y

        # --- ОБНОВЛЕНИЕ ЛЕТУЧИХ МЫШЕЙ ---
        for bat in self.scene["Enemies"]:
            bx = self.player_sprite.center_x - bat.center_x
            by = self.player_sprite.center_y - bat.center_y
            bd = math.sqrt(bx*bx + by*by)

            if bd < 1200:
                bat.center_x = bat.center_x + (bx / bd) * ENEMY_SPEED
                bat.center_y = bat.center_y + (by / bd) * ENEMY_SPEED

            if arcade.check_for_collision(self.player_sprite, bat):
                self.take_damage(ENEMY_DAMAGE)

            if time.time() - self.last_attack_time > 0.3:
                bat.color = arcade.color.WHITE

        # --- ОБНОВЛЕНИЕ БОССА ---
        if len(self.scene["Boss"]) > 0:
            b_obj = self.scene["Boss"][0]
            self.boss_ai_tick(b_obj, delta_time)

            if arcade.check_for_collision(self.player_sprite, b_obj):
                # Урон от касания босса теперь всего 8
                self.take_damage(BOSS_COLLISION_DAMAGE)

        # --- ОБНОВЛЕНИЕ ПРИЗРАКОВ ---
        for ghost in self.scene["Ghosts"]:
            gx = self.player_sprite.center_x - ghost.center_x
            gy = self.player_sprite.center_y - ghost.center_y
            gdist = math.sqrt(gx*gx + gy*gy)

            if gdist > 600:
                ghost.center_x = ghost.center_x + (gx / gdist) * GHOST_SPEED
                ghost.center_y = ghost.center_y + (gy / gdist) * GHOST_SPEED
            elif gdist < 450:
                ghost.center_x = ghost.center_x - (gx / gdist) * GHOST_SPEED
                ghost.center_y = ghost.center_y - (gy / gdist) * GHOST_SPEED

            if time.time() - ghost.last_shoot_time > GHOST_SHOOT_DELAY:
                if gdist < 1100:
                    self.make_projectile(ghost, gx, gy, gdist)
                    ghost.last_shoot_time = time.time()

            if arcade.check_for_collision(self.player_sprite, ghost):
                self.take_damage(10)

            if time.time() - self.last_attack_time > 0.3:
                ghost.color = arcade.color.WHITE

        # --- ОБНОВЛЕНИЕ ПУЛЬ ---
        for bullet in self.scene["Projectiles"]:
            bullet.update()

            if arcade.check_for_collision(self.player_sprite, bullet):
                self.take_damage(bullet.damage)
                bullet.remove_from_sprite_lists()

            if abs(bullet.center_x - self.player_sprite.center_x) > 2500:
                bullet.remove_from_sprite_lists()

        # --- ЭФФЕКТЫ ИГРОКА ---
        if time.time() - self.last_hit_time < 0.2:
            self.player_sprite.alpha = 150
        else:
            self.player_sprite.alpha = 255

        if time.time() - self.last_attack_time < ATTACK_DURATION:
            if self.is_facing_right:
                self.player_sprite.texture = self.textures["player_attack_r"]
            else:
                self.player_sprite.texture = self.textures["player_attack_l"]
        else:
            if self.is_facing_right:
                self.player_sprite.texture = self.textures["player_r"]
            else:
                self.player_sprite.texture = self.textures["player_l"]

        # ПОРТАЛ
        if self.current_level == 1:
            if len(self.scene["Portal"]) > 0:
                if arcade.check_for_collision(self.player_sprite, self.scene["Portal"][0]):
                    self.setup(2)

        # ПАДЕНИЕ В БЕЗДНУ
        if self.player_sprite.center_y < -600:
            self.take_damage(25)
            if self.player_hp > 0:
                self.player_sprite.position = (200, 600)

    def make_projectile(self, from_obj, dx, dy, dist, dmg=8, size=0.3):
        """ Создает снаряд. """
        if dist == 0: return
        vx = (dx / dist) * PROJECTILE_SPEED
        vy = (dy / dist) * PROJECTILE_SPEED
        p = Bullet(self.textures["projectile"], size, vx, vy, dmg)
        p.position = from_obj.position
        self.scene.add_sprite("Projectiles", p)

    def do_player_attack(self):
        """ Метод атаки. """
        if self.game_state != STATE_GAME: return
        self.last_attack_time = time.time()
        if self.sound_attack: arcade.play_sound(self.sound_attack)

        target_lists = ["Enemies", "Ghosts", "Boss"]
        for list_name in target_lists:
            for target in self.scene[list_name]:
                if arcade.get_distance_between_sprites(self.player_sprite, target) < ATTACK_RANGE:
                    target.hp = target.hp - PLAYER_DAMAGE
                    target.color = arcade.color.RED
                    if target.hp <= 0:
                        target.remove_from_sprite_lists()
                        if self.current_level == 2:
                            if len(self.scene["Boss"]) == 0:
                                self.game_state = STATE_WIN

    def take_damage(self, amount):
        """ Метод получения урона. """
        if self.player_hp <= 0: return
        if time.time() - self.last_hit_time < INVULNERABILITY_TIME: return

        self.player_hp = self.player_hp - amount
        if self.player_hp < 0: self.player_hp = 0

        self.last_hit_time = time.time()
        if self.sound_hit: arcade.play_sound(self.sound_hit)
        self.player_sprite.change_y = 15

        if self.player_hp <= 0:
            self.game_state = STATE_GAME_OVER

    def on_key_press(self, key, modifiers):
        """ Клавиатура. """
        if self.game_state == STATE_MENU:
            if key == arcade.key.ENTER: self.setup(1)
            return

        if self.game_state == STATE_GAME:
            if key == arcade.key.P or key == arcade.key.ESCAPE:
                self.game_state = STATE_PAUSE
            elif key in [arcade.key.UP, arcade.key.W, arcade.key.SPACE]:
                if self.physics_engine.can_jump():
                    self.player_sprite.change_y = PLAYER_JUMP_SPEED
                    arcade.play_sound(self.sound_jump)
            elif key in [arcade.key.LEFT, arcade.key.A]:
                self.player_sprite.change_x, self.is_facing_right = -PLAYER_SPEED, False
            elif key in [arcade.key.RIGHT, arcade.key.D]:
                self.player_sprite.change_x, self.is_facing_right = PLAYER_SPEED, True
            elif key == arcade.key.X: self.do_player_attack()

        elif self.game_state == STATE_PAUSE:
            if key == arcade.key.P or key == arcade.key.ESCAPE:
                self.game_state = STATE_GAME

        elif self.game_state == STATE_GAME_OVER:
            if key == arcade.key.R: self.setup(1)
            elif key == arcade.key.Q: self.game_state = STATE_MENU

    def on_key_release(self, key, modifiers):
        if key in [arcade.key.LEFT, arcade.key.A, arcade.key.RIGHT, arcade.key.D]:
            self.player_sprite.change_x = 0

# --- ЗАПУСК ---
if __name__ == "__main__":
    game = MyGame()
    arcade.run()