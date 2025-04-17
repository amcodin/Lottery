I used `#` for the main title and `##` for section headings.
The version/date line is *italicized*.
Mathematical formulas are enclosed in `$...$` for inline math and `$$...$$` for display math, using LaTeX syntax. This requires a Markdown renderer that supports LaTeX (like MathJax or KaTeX).
The combination notation $\binom{n}{r}$ (written as `\binom{n}{r}`) is used for clarity.
I've added the calculated intermediate values in the probability calculations for clarity (e.g., $\binom{6}{4}=15$, $\binom{43}{2}=903$).
The approximate symbol `≈` (written as `\approx`) is used where the original document indicated an approximation.
I added a small clarifying note about the implicit selection of the single bonus number in the "Winning with the bonus" section formula.

# CALCULATING THE PROBABILITIES OF WINNING LOTTO 6/49

*VERSION 3: MARCH 1, 2003*

The probability of event tells us how likely it is that the event will occur and is always a value between 0 and 1 (e.g. "there is a 50% chance of rain tomorrow" means that the probability of rain is .50, or "that team has a 1 in 1000 shot at winning" means that the probability that the team will win is $\frac{1}{1000} = .001$). A random event is very likely to happen if its probability is close to 1 and it is not likely to happen if the probability is close to 0.

In the lottery, the probability of winning will be equal to the fraction of all of the possible lottery numbers which count as winning. That is,

$$
\text{the probability of winning the lottery} = \frac{\text{the number of winning lottery numbers}}{\text{the total number of possible lottery numbers}}
$$

In order to find the probability of winning the lottery we will have to figure out “the number of winning lottery numbers" and "the total number of possible lottery numbers."

The number of ways of picking $r$ items from a set of $n$ items is denoted by $\binom{n}{r} = \frac{n!}{r!(n-r)!}$ where $n!$ represents $n \times (n - 1) \times (n - 2) \times \dots \times 2 \times 1$. The number of ways of picking 2 items from a set of 5 items is by this formula: $\binom{5}{2} = \frac{5!}{2!(5-2)!} = \frac{5!}{2!3!} = \frac{120}{2 \times 6} = \frac{120}{12} = 10$. That is, if our set of 5 items is {1, 2, 3, 4, 5} then we can pick the following 10 groups of 2 items: {1,2}, {1,3}, {1,4}, {1,5}, {2,3}, {2,4}, {2,5}, {3,4}, {3,5}, {4,5}.

This is exactly what is needed to find the number of possible lottery numbers because in the lottery 6 numbers are chosen from a set of size 49. Since the number of ways of picking of 6 numbers from a set of 49 different numbers is $\binom{49}{6} = 13,983,816$, this is equal to the total number of possible 6/49 tickets.

In order to win the large jackpot in the lottery you must hold a winning ticket which matches all 6 of the winning numbers and there is exactly one set of winning lottery numbers. Therefore,

$$
\text{the probability of winning the large jackpot in the 6/49 lottery} = \frac{1}{13,983,816}
$$

To figure out the probability of winning the other prizes in the lottery the method is always the same, determine the number of possible winning numbers and then divide by the total number of possible lottery numbers.

## Winning without the bonus

Some of the prize categories for the other jackpots are for matching "4 of the 6 winning numbers" or "3 of the 6 winning numbers." There are 6 numbers on a ticket which wins these prizes. To match $k$ of the winning numbers, we must select $k$ of 6 winning numbers AND we must select $(6-k)$ of the 43 non-winning numbers. Therefore there are $\binom{6}{k} \times \binom{43}{6-k}$ possible winning tickets matching $k$ of the winning numbers.

$$
\text{probability of having 4 of 6 winning numbers} = \frac{\binom{6}{4}\binom{43}{2}}{\binom{49}{6}} = \frac{15 \times 903}{13,983,816} = \frac{13,545}{13,983,816} \approx \frac{1}{1033}
$$

$$
\text{probability of having 3 of 6 winning numbers} = \frac{\binom{6}{3}\binom{43}{3}}{\binom{49}{6}} = \frac{20 \times 12,341}{13,983,816} = \frac{246,820}{13,983,816} \approx \frac{1}{57}
$$

There is an exception to this in the condition if we insist that the ticket not include the bonus number (e.g. the prize for “5 of 6 winning numbers and not the bonus" because the tickets with "5 of 6 winning numbers and the bonus" win a bigger prize). In this case, the number of tickets which include $k$ winning numbers AND $6-k$ of the 42 non-winning numbers which are not the bonus will be $\binom{6}{k} \times \binom{42}{6-k}$.

$$
\text{probability of having 5 of 6 winning numbers and not the bonus} = \frac{\binom{6}{5}\binom{42}{1}}{\binom{49}{6}} = \frac{6 \times 42}{13,983,816} = \frac{252}{13,983,816} \approx \frac{1}{55491}
$$

## Winning with the bonus

The number of tickets which have $k$ winning numbers and the bonus can be found by choosing $k$ of the 6 winning numbers AND the bonus number AND choosing $5-k$ of the 42 non-winning/non-bonus numbers. This means that there are $\binom{6}{k} \times \binom{42}{5-k}$ tickets which include exactly $k$ winning numbers and the bonus. (*Note: This assumes choosing the 1 bonus number is implicit, the full combination would be $\binom{6}{k}\binom{1}{1}\binom{42}{5-k}$*).

$$
\text{probability of having 5 of 6 winning numbers and the bonus} = \frac{\binom{6}{5}\binom{42}{0}}{\binom{49}{6}} = \frac{6 \times 1}{13,983,816} = \frac{6}{13,983,816} = \frac{1}{2,330,636}
$$