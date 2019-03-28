from random import randint, uniform, random, choice
from math import sqrt
from statistics import mean
import csv
from time import time
import os
import pygame as pg
import pygame.gfxdraw
from pygame.math import Vector2 as vec


# change directory where the script is
os.chdir(os.path.abspath(os.path.dirname(__file__)))

### CONFIGURATION ###
WIN_WIDTH = 1280
WIN_HEIGHT = 800
FPS = 30
BACKGROUND_COLOR = (7, 7, 7)
FOOD_COLOR = (50, 50, 255)
POISON_COLOR = (255, 50, 50)

SAVE_TO_CSV = False
CSV_NAME = str(int(time())) + "_data.csv"
SAVE_DELAY = 20 * 1000  # in milliseconds

# Switches how we choose the creatures that breed, with this
# only the creature with the record age will breed, even if it died already
ONLY_RECORD_BREEDS = False

TOTAL_CREATURES = 10
MIN_CREATURE_SIZE = 7
MAX_CREATURE_SIZE = 53

# chance to spawn a new creature to add variation to the simulation
# if this fails an existing creature will try to breed
# keep it low to favor breeding
# if 0 creatures are alive, then spawn_creatures function will spawn in bulk
NEW_CREATURE_CHANCE = 0.003

DNA_SIZE = 7  # number of values in the dna.

# below values are affected by the fitness of the creature
# breed_chance = x / (BREED_CHANCE_VALUE + x);  x --> fitness
BREED_CHANCE_VALUE = 850
MAX_MUTATION_VALUE = 0.2  # how much a property will change when mutated

MUTATION_CHANCE = 0.1  # chance to mutate each property, not affected by fitness

# this should avoid that a new creature spawns directly eating poison or food
# but with (MAX_CREATURE_SIZE // 2) + 1 we won't avoid bigger creatures to pass between
# food/posion that are too close
# biggest gaps make it look ugly and unreal...
DISTANCE_BETWEEN_SPRITES = (MAX_CREATURE_SIZE // 2) + 1

TOTAL_POISON = 69
TOTAL_FOOD = 62
HEALTH_DEGENERATION = 9.1  # creatures will lose hp per second
POISON_VALUE = -41  # negative value as poison is bad!
FOOD_VALUE = 17

# Values that will vary according to DNA changes, but have a max value
MAX_STEER_FORCE = 4
MAX_PERCEPTION_DIST = 300  # max dist at which creatures can evolve to see food & poison
# the highter dir_angle_mult a creature has, the higher priority for targets in front of it
MIN_DIR_ANGLE_MULT = 1
MAX_DIR_ANGLE_MULT = 5
# Creatures have a constraint, they evolve choosing between maxvel and maxhealth
# having more maxhealth means bigger size and less maxvel
TOTAL_MAXVEL_MAXHP_POINTS = 250
# we don't want creatures to spawn with HP values lower than this
# very low values make no sense because they die with health degeneration too fast
MIN_HP = 30


# When the creature finds no food or poison, it wanders
# wander ring properties:
WANDER_RING_DISTANCE = (WIN_WIDTH + WIN_HEIGHT) // 8
WANDER_RING_RADIUS = (WIN_WIDTH + WIN_HEIGHT) // 4
WANDER_RING_WAIT = 2000


def translate(value, left_min, left_max, right_min, right_max):
    """ returns scaled value from the ranges of the left to right """
    # Figure out how 'wide' each range is
    left_span = left_max - left_min
    right_span = right_max - right_min
    # Convert the left range into a 0-1 range (float)
    value_scaled = float(value - left_min) / float(left_span)
    # Convert the 0-1 range into a value in the right range.
    return right_min + (value_scaled * right_span)


class Creature(pg.sprite.Sprite):
    def __init__(self, pos, dna=None):
        super().__init__()

        self.dna = []
        # if we don't have dna, create a random one
        if dna is None:
            for _ in range(DNA_SIZE):
                self.dna.append(random())
        else:
            self.dna = dna

        # Apply dna values !!
        # dna[0] maps size, max_health and max_vel
        max_vel_value = TOTAL_MAXVEL_MAXHP_POINTS - MIN_HP
        self.max_vel = translate(self.dna[0], 0, 1, MIN_HP, max_vel_value)
        self.max_health = TOTAL_MAXVEL_MAXHP_POINTS - self.max_vel
        self.size = int(translate(self.max_health, MIN_HP, max_vel_value,
                                  MIN_CREATURE_SIZE, MAX_CREATURE_SIZE))

        # we need to calc this when we have the creature size
        # Guarantee odd number, for drawing
        if self.size % 2 == 0:
            self.size += 1
        radius = (self.size - 1) // 2
        self.radius = radius

        # keep applying DNA values
        self.food_attraction = translate(self.dna[1], 0, 1, -20, 20)
        self.poison_attraction = translate(self.dna[2], 0, 1, -20, 20)
        self.food_dist = translate(
            self.dna[3], 0, 1, self.radius, MAX_PERCEPTION_DIST)
        self.poison_dist = translate(
            self.dna[4], 0, 1, self.radius, MAX_PERCEPTION_DIST)
        self.max_steer_force = translate(self.dna[5], 0, 1, 0, MAX_STEER_FORCE)
        self.dir_angle_mult = translate(
            self.dna[6], 0, 1, MIN_DIR_ANGLE_MULT, MAX_DIR_ANGLE_MULT)

        # required to draw the creature, the variable name must be "image" for pygame sprite.
        self.image = pg.Surface((self.size, self.size), pg.SRCALPHA)
        self.orig_image = self.image
        self.rect = self.image.get_rect(center=pos)

        # this is for drawing something similar eyes
        self.eye_radius = self.radius // 3

        self.color = pg.Color('green')
        self.pos = pos
        self.vel = vec(0.0, 0.0)
        self.acc = vec(0.0, 0.0)
        self.desired = vec(0.0, 0.0)  # drawing purposes
        self.age = 0
        self.eaten = 0
        self.childs = 0
        self.gen = 0

        self.health = self.max_health

        self.last_target_time = 0
        self.wander_ring_pos = self.pos

    def fitness(self):
        """ returns fitness value of this creature """
        return sqrt(self.age + self.eaten * 2)

    def mutate(self, dna):
        """ returns a mutated (or not) copy of its own dna """
        # range value in which the dna can mutate
        mutation_range = MAX_MUTATION_VALUE/((self.fitness()*0.1)**2 + 1)
        for i in range(DNA_SIZE):
            if random() < MUTATION_CHANCE:
                # random offset based on mutation range
                offset = translate(random(),
                                   0, 1,
                                   -mutation_range, mutation_range)
                print(f"[{pg.time.get_ticks()}] [{id(self)}] " +
                      f"mutating [{i}] (range:{mutation_range}, " +
                      f"offset:{offset}): {dna[i]} --> ", end="")
                # apply the offset
                dna[i] += offset
                # ensure we aren't out of limits
                dna[i] = max(0, min(dna[i], 1))
                print(f"{dna[i]}")
        return dna

    def breed(self):
        # higher fitness = higher chance to breed
        x = self.fitness()
        if random() < (x / (BREED_CHANCE_VALUE + x)):
            return self.mutate(self.dna.copy())
        return None

    def seek(self, target):
        desired = target - self.pos
        if desired.length() > 0.001:
            desired = desired.normalize() * self.max_vel
        self.desired = desired
        steer = desired - self.vel
        if steer.length() > self.max_steer_force:
            steer.scale_to_length(self.max_steer_force)
        return steer

    def wander_by_ring(self):
        now = pg.time.get_ticks()
        if now - self.last_target_time > WANDER_RING_WAIT:
            self.last_target_time = now
            new_pos = vec((randint(0, int(WIN_WIDTH)),
                           randint(0, int(WIN_HEIGHT))))
            if self.vel.length():
                self.wander_ring_pos = new_pos + self.vel.normalize() * WANDER_RING_DISTANCE
            else:
                self.wander_ring_pos = new_pos * WANDER_RING_DISTANCE

        target = self.wander_ring_pos + \
            vec(WANDER_RING_RADIUS, 0).rotate(uniform(0, 360))

        # self.wander_target = target  # only for drawing its vector
        self.apply_force(self.seek(target))

    def seek_targets(self, targets):
        # we start with a force of 0 length
        desired = vec(0.0, 0.0)

        # create a dict with all the targets in range
        targets_inrange = {}
        for t in targets:
            dist = (self.pos - t.pos).length()
            if t.is_poison:
                if dist <= self.poison_dist:
                    targets_inrange[t] = dist
            else:
                if dist <= self.food_dist:
                    targets_inrange[t] = dist

        if targets_inrange:
            min_dist = min(targets_inrange.values())
            for t, dist in targets_inrange.items():
                # get the desired vector to the target pos
                desired_force = t.pos - self.pos
                # normalize it if possible
                if desired_force.length() > 0.001:
                    desired_force.scale_to_length(self.max_vel)

                # calculate the difference in angle between
                # the target and our velocity, less difference will have
                # a priority (targets we have in front)
                _, angle_d = desired_force.as_polar()
                _, angle = self.vel.as_polar()
                angle_diff = abs(angle - angle_d)

                min_dist_mult = 1
                if dist == min_dist:
                    min_dist_mult = 2

                if t.is_poison:
                    desired_force *= self.poison_attraction * min_dist_mult
                else:
                    desired_force *= self.food_attraction * min_dist_mult

                # adjust vector with distance and dir angle
                # the higher dir_angle_mult a creature has, the higher priority
                # targets in front of it will have (i'm proud of this ^^)
                desired_force /= (1 + dist +
                                  sqrt(angle_diff * self.dir_angle_mult))

                # sum all the force
                desired += desired_force

            # in case force is too low
            desired *= self.max_vel
            if desired.length() > self.max_vel:
                desired.scale_to_length(self.max_vel)

            self.desired = desired

            # calc the steer force
            steer = desired - self.vel

            if steer.length() > self.max_steer_force:
                steer.scale_to_length(self.max_steer_force)
            # finally apply the steer to the acc
            self.apply_force(steer)
        else:
            # nothing in range, go wander
            self.wander_by_ring()

    def apply_force(self, force):
        self.acc += force

    def eat(self, is_poison):
        if is_poison:
            self.health += POISON_VALUE
        else:
            self.health += FOOD_VALUE
            self.eaten += 1
        self.health = max(0, min(self.health, self.max_health))

    def update(self, dt, targets):
        self.seek_targets(targets)

        self.vel += self.acc
        if self.vel.length() > self.max_vel:
            self.vel.scale_to_length(self.max_vel)

        self.pos += self.vel * dt
        self.rect.center = self.pos

        self.health -= HEALTH_DEGENERATION * dt
        self.acc *= 0  # RESET ACC
        self.age += dt
        self.draw_image()

    def is_dead(self):
        return self.health <= 0

    def draw_image(self):
        green = translate(self.health, 0, self.max_health, 0, 255)
        green = max(0, min(green, 255))
        red = 255 - green
        self.color = (red, green, 35)

        pg.gfxdraw.filled_circle(self.orig_image, self.radius, self.radius, self.radius,
                                 self.color)
        pg.gfxdraw.filled_circle(self.orig_image, self.size - self.eye_radius,
                                 abs(self.radius - self.eye_radius - 2), abs(self.eye_radius - 2), (red, red, green))
        pg.gfxdraw.filled_circle(self.orig_image, self.size - self.eye_radius,
                                 self.radius + self.eye_radius + 2, abs(self.eye_radius - 2), (red, red, green))

        # rotate image
        # where the creature is going
        _, angle = self.vel.as_polar()  # get direction angle
        # transform with the negative angle
        self.image = pg.transform.rotate(self.orig_image, -angle)
        # update rect position
        self.rect = self.image.get_rect(center=self.rect.center)

    def draw_vectors(self, screen):
        scale = 2

        # food distance
        pg.draw.circle(screen, FOOD_COLOR,
                       (int(self.pos.x), int(self.pos.y)), int(self.food_dist), 1)
        # poison distance
        pg.draw.circle(screen, POISON_COLOR,
                       (int(self.pos.x), int(self.pos.y)), int(self.poison_dist), 1)

        # food / poison attraction
        if self.vel.length():
            direction = self.vel.normalize()
        else:
            direction = self.vel
        pg.draw.line(screen, FOOD_COLOR, self.pos,
                     (self.pos + (direction * self.food_attraction) * scale), 2)
        pg.draw.line(screen, POISON_COLOR, self.pos,
                     (self.pos + (direction * self.poison_attraction) * scale), 2)


class Food(pg.sprite.Sprite):
    def __init__(self, pos, size, is_poison=False):
        super().__init__()

        # Guarantee odd number, for drawing
        if size % 2 == 0:
            size += 1

        radius = (size - 1) // 2
        self.radius = radius

        self.image = pg.Surface((size, size), pg.SRCALPHA)
        self.rect = self.image.get_rect(center=pos)

        self.is_poison = is_poison
        self.color = POISON_COLOR if self.is_poison else FOOD_COLOR

        pg.gfxdraw.filled_circle(self.image, radius, radius, radius,
                                 self.color)

        self.pos = pos


def valid_pos(newpos, sprites):
    """ checks if given position respects given distance between sprites """
    mindist = DISTANCE_BETWEEN_SPRITES
    valid = True
    for s in sprites:
        if (newpos - s.pos).length() < mindist:
            valid = False
            break
    return valid


def process_collisions(group1, group2):
    # check for food collisions
    hits = pg.sprite.groupcollide(group1, group2, False, True,
                                  collided=pg.sprite.collide_circle_ratio(1.0))
    if hits:
        for creature in hits:
            for food in hits[creature]:
                creature.eat(food.is_poison)
                # kill and remove the food
                food.kill()  # should be killed already as its set to True in groupcollide
                del food  # delete instanciated object


def print_info(v):
    print(f"\n[{pg.time.get_ticks()}] [{id(v)}] [Fitness: {v.fitness()}] Age: {v.age} seconds." +
          f" F.Eaten: {v.eaten}\n" +
          f"currHP: {v.health}, Gen: {v.gen}, Childs: {v.childs}\n" +
          f"DNA: {v.dna}\n" +
          f"FoodAttr: {v.food_attraction}, PoisonAttr: {v.poison_attraction}\n" +
          f"FoodDist: {v.food_dist}, PoisonDist: {v.poison_dist}\n" +
          f"MaxHealth: {v.max_health}, MaxVel: {v.max_vel}, Size: {v.size}\n" +
          f"MaxSteer: {v.max_steer_force}, DirAngleMult: {v.dir_angle_mult}\n")


class Game:
    def __init__(self):
        self.screen = pg.display.set_mode((WIN_WIDTH, WIN_HEIGHT), pg.SRCALPHA)
        self.clock = pg.time.Clock()
        pg.init()
        self.running = True

        self.draw_vectors = False
        self.only_record_breeds = ONLY_RECORD_BREEDS
        self.save_to_csv = SAVE_TO_CSV

        # record creature tracking
        self.record = None
        self.age_record = 0
        self.fitness_record = 0
        self.current_record = None

        # used to save csv file
        self.history = []
        self.perm_hist = []
        header = ["Time", "Fitness", "Age", "FEaten", "MaxVel_MaxHP", "FoodAttraction",
                  "PoisonAttraction", "FoodDistance", "PoisonDistance", "MaxSteerForce",
                  "DirAngleMult"]
        self.history.append(header)
        self.perm_hist.append(header)
        self.last_save = 0  # last time csv data was saved

        # all the sprite groups
        self.all_sprites = pg.sprite.Group()
        self.all_creatures = pg.sprite.Group()
        self.all_foods = pg.sprite.Group()
        self.poison_group = pg.sprite.Group()
        self.food_group = pg.sprite.Group()

    def events(self):
        # Events here, without pg.event.get() or pg.event.wait() window becomes irresponsibe
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            # this will process they keystroke once, without repeating if holded down
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    self.running = False
                elif event.key == pg.K_v:
                    self.draw_vectors = not self.draw_vectors
                elif event.key == pg.K_r:
                    self.only_record_breeds = not self.only_record_breeds
                elif event.key == pg.K_s:
                    self.save_to_csv = not self.save_to_csv
                elif event.key == pg.K_p:
                    print(
                        f"\n[{pg.time.get_ticks()}] [total creatures: {len(self.all_creatures)}]\n")
                    if self.current_record is not None:
                        print("Current record info:")
                        print_info(self.current_record)
                    if self.record is not None:
                        print("All times record info:")
                        print_info(self.record)

    def key_events(self):
        pass
        # this will trigger the action meanwhile the key is pressed down
        # pressed = pg.key.get_pressed()
        # if pressed[pg.K_LEFT]:
        # move left

    def check_record(self):
        # check for the current record and global record of creature age
        current_record = None
        current_fitness_record = 0
        for c in self.all_creatures:
            # record of all times:
            if c.fitness() > self.fitness_record:
                self.age_record = c.age
                self.fitness_record = c.fitness()
                if self.record is not None and c is not self.record:
                    print("\n---------------------- New Record --------------------")
                    print("old:")
                    print_info(self.record)
                    print("new:")
                    print_info(c)
                    print("------------------------------------------------------")
                self.record = c

            # current age record creature:
            if c.fitness() > current_fitness_record:
                current_fitness_record = c.fitness()
                current_record = c
                self.current_record = c

        if current_record is not None:
            pg.gfxdraw.filled_circle(self.screen, int(current_record.pos.x),
                                     int(current_record.pos.y),
                                     current_record.radius // 4, pg.Color('black'))

    def spawn_creatures(self):
        # spawn a new creature or try to breed existing one
        # we always try to spawn a full set of creatures if there are 0
        loops = 1
        if not self.all_creatures:
            loops = TOTAL_CREATURES

        if random() < NEW_CREATURE_CHANCE or not self.all_creatures:
            if len(self.all_creatures) < TOTAL_CREATURES:
                for _ in range(loops):
                    newpos = vec(randint(0, WIN_WIDTH),
                                 randint(0, WIN_HEIGHT))
                    if valid_pos(newpos, self.poison_group):
                        newcreature = Creature(newpos)
                        self.all_creatures.add(newcreature)
                        self.all_sprites.add(newcreature)
        else:
            # we can breed if all_creatures is not empty and we still have room
            if len(self.all_creatures) < TOTAL_CREATURES and self.all_creatures:
                # we pick one random sprite as a parent and try to breed it
                parent = self.record if self.only_record_breeds else choice(
                    self.all_creatures.sprites())
                dna = parent.breed()
                if dna is not None:
                    # breed was successful, see if it's lucky to find a valid position to spawn
                    newpos = vec(randint(0, WIN_WIDTH),
                                 randint(0, WIN_HEIGHT))
                    if valid_pos(newpos, self.poison_group):
                        # got a valid position, create a new creature there with dna as heritage
                        child = Creature(newpos, dna)
                        self.all_creatures.add(child)
                        self.all_sprites.add(child)
                        parent.childs += 1  # the parent, augments its childs counter
                        child.gen += 1 + parent.gen  # update the childs gen by 1 + parents gen

    def spawn_foods(self):
        # spawn poison
        if len(self.poison_group) < TOTAL_POISON:
            newpos = vec(randint(0, WIN_WIDTH), randint(0, WIN_HEIGHT))
            if valid_pos(newpos, self.all_sprites):
                f = Food(newpos, 5, True)
                self.all_foods.add(f)
                self.poison_group.add(f)
                self.all_sprites.add(f)
        # spawn food
        if len(self.food_group) < TOTAL_FOOD:
            newpos = vec(randint(0, WIN_WIDTH), randint(0, WIN_HEIGHT))
            if valid_pos(newpos, self.all_sprites):
                f = Food(newpos, 5, False)
                self.all_foods.add(f)
                self.food_group.add(f)
                self.all_sprites.add(f)

    def append_to_hist(self, creature):
        row = []
        row.append(pg.time.get_ticks())
        row.append(creature.fitness())
        row.append(creature.age)
        row.append(creature.eaten)
        for i in range(DNA_SIZE):
            row.append(creature.dna[i])
        self.history.append(row)
        self.perm_hist.append(row)

    def print_average(self):
        print("")

        def isfloat(value):
            """ returns true if value can be a float """
            try:
                float(value)
                return True
            except ValueError:
                return False

        def column(matrix, i):
            """ returns the column of index i removing headers """
            return [row[i] for row in matrix if isfloat(row[i])]

        # last SAVE_DELAY millisecs average fitness
        average = 0
        if self.history:
            fitness_col = column(self.history, 1)
            if fitness_col:
                average = mean(fitness_col)
            if average:
                print(
                    f"[{pg.time.get_ticks()}] - Last {SAVE_DELAY // 1000} secs Fitness Average: {average}")

        # All time average fitness
        average = 0
        if self.perm_hist:
            fitness_col = column(self.perm_hist, 1)
            if fitness_col:
                average = mean(fitness_col)
            if average:
                print(
                    f"[{pg.time.get_ticks()}] - All time Fitness Average: {average}")
        print("")

    def game_loop(self):
        while self.running:
            # get delta time in seconds (default is miliseconds)
            dt = self.clock.get_time() / 1000

            # spawn/breed, we check poison group just to ensure that none spawns eating poison
            self.spawn_creatures()
            # food/poison, we check all the sprites not to spawn food on top of anything
            self.spawn_foods()

            self.events()
            self.key_events()

            self.all_creatures.update(dt, self.all_foods)
            # check if any creature died
            for creature in self.all_creatures:
                if creature.is_dead():
                    self.append_to_hist(creature)
                    creature.kill()
                    del creature

            process_collisions(self.all_creatures, self.all_foods)

            self.screen.fill(BACKGROUND_COLOR)

            self.all_sprites.draw(self.screen)

            if self.draw_vectors:
                for c in self.all_creatures:
                    c.draw_vectors(self.screen)

            self.check_record()

            pg.display.flip()

            if self.record is not None:
                csv_out = ""
                if self.save_to_csv:
                    csv_out = f"(Saving csv to: {CSV_NAME})"
                pg.display.set_caption(
                    "Fittest Creature (Fps: {:.2f}) ".format(self.clock.get_fps()) +
                    f"(Running: {int(pg.time.get_ticks() / 1000)} seconds) (Alive: {len(self.all_creatures)}) " +
                    f"(Record: {int(self.age_record)} secons) " +
                    "(Record fitness: {:.2f}) ".format(self.record.fitness()) +
                    f"(Only record breeds: {str(self.only_record_breeds)}) {csv_out}")

            # save to csv every X secs
            if self.save_to_csv:
                now = pg.time.get_ticks()
                if now - self.last_save > SAVE_DELAY:
                    self.last_save = now
                    with open(CSV_NAME, mode='a', newline='') as data_file:
                        data_writer = csv.writer(
                            data_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                        for line in self.history:
                            data_writer.writerow(line)
                    self.print_average()
                    self.history.clear()

            # last action before repeating the loop, let the time run!
            self.clock.tick(FPS)

    def run(self):
        self.game_loop()
        # if we quit the game loop, the game has ended
        pg.quit()


if __name__ == "__main__":
    game = Game()
    game.run()
