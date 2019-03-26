# fittest_ship
Evolutionary steering behaviours with genetic algorithm written in python

## Disclaimer

This is more of a remainder for myself if I forget how does it work in the future, but I hope it helps anyone interested in python and genetic algorithms.

## Details

The **fittest_ship.py** script was just me learning pygame and experimenting with genetic algorithms.


In **fittest_creature.py** the spawned creatures try to survive, the longer they live the more childs they will have.

All the creatures have a variable that stores its DNA in the form of an array, each item in the array corresponds to a number from 0 to 1 and is linked to a property or a "phenotype" of the creature.


The environment is simple, there is good food, and poison, if a creature eats food it will gain health, if it eats poison it will lose some. The values can be changed in the configuration variables at the top of the script.

Creatures spawn with random DNA values, here is an example:

```
dna[0] = 0.2774876569919621  --> MaxHealth: 145.60197488128608, MaxVel: 74.39802511871393, Size: 41
dna[1] = 0.7841259541028673  --> FoodAttr: 11.365038164114694
dna[2] = 0.3977295324539377  --> PoisonAttr: -4.09081870184249
dna[3] = 0.7463319410665977  --> FoodDist: 154.3397493919876
dna[4] = 0.6083194845586946  --> PoisonDist: 129.497507220565
```

As you can see above, dna[0] is mapped to three properties, max health, max velocity and size of the creature, I just thought it would make it more interesting. Code wise I just distribute points between max vel and max health, and then the more health it has the bigger it will be.

The creature above has some nice properties to survive, its attracted to food (positive value) and avoids poison (negative value), can see food at a range of 154 and poison at a range of 129.


### How does the genetic algorithm work here

Basically, each creature has a variable called "age", which stores its age in seconds, when a creature has more than the value defined in "BREEDING_AGE" variable, it will have a chance to breed (which is higher the more age it has). That way we can establish that the age property will be the fitness value of this algorithm.


The breed function of the creature returns a mutated version of its own DNA, there is a chance to mutate each property, and a total amout that property can mutate, both values **decrease** as the creature has more age.
So, the more age a creature has, the less chance to mutate any property, and if it mutates, the difference in values will be lower, that way when we have a bad population (bad = age is low) creatures will mutate more.
Then that mutated DNA is used to spawn a new creature.

When we have a pool of creatures with age > BREEDING_AGE, they will try to breed randomly. We can turn on "ONLY_RECORD_BREEDS" so that only the creature that has the current all time age record can breed, even if that creature is dead, which I guess will find creatures with better fitness faster.

There are a few more variables playing into this, the code has a lot of comments explaining it, and it being written in python is pretty well readable :)

### Misc

- Press **v** to turn on/off a visual representation of food/poison properties of the creatures.
- Press **r** to turn on/off only record can breed. (current mode can be seen on status bar)
- Press **s** to turn on/off save to csv file. (current mode can be seen on status bar).
_(Each time a creature dies, its age followed by its DNA will be stored in a *.csv file in the same directory as the script. It can be disabled by setting the variable SAVE_TO_CSV to False. Nice for creating charts...)_
- Press **p** to print to the console information about the current creature age record and the all time record.
