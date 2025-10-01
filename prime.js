function isPrime(n) {
  if (n < 2) return false;
  if (n === 2) return true;
  if (n % 2 === 0) return false;
  let i = 3;
  while (i * i <= n) {
    if (n % i === 0) return false;
    i += 2;
  }
  return true;
}

function intToRoman(n) {
  if (!(1 <= n && n <= 3999)) {
    throw new Error("intToRoman supports values from 1 to 3999");
  }
  const numerals = [
    [1000, "M"], [900, "CM"], [500, "D"], [400, "CD"],
    [100, "C"], [90, "XC"], [50, "L"], [40, "XL"],
    [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"],
  ];
  let result = [];
  for (let [value, symbol] of numerals) {
    if (n === 0) break;
    const count = Math.floor(n / value);
    n %= value;
    if (count > 0) {
      result.push(symbol.repeat(count));
    }
  }
  return result.join("");
}

for (let i = 1; i <= 1000; i++) {
  const rn = intToRoman(i);
  console.log(`${rn}${isPrime(i) ? '*' : ''}`);
}
