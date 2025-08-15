# ═══ STEP 2: UNDERSTANDING SHRINKAGE MATHEMATICALLY ═══

print("=== Step 2: Understanding 'Shrinkage' ===")
print()

# The CORE IDEA: Blend two values based on confidence
# 
# Formula: final_value = (confidence × my_estimate) + ((1 - confidence) × reference_value)
#
# Think of it like this:
# - If confidence = 1.0 (100% confident) → Use my_estimate entirely
# - If confidence = 0.0 (0% confident) → Use reference_value entirely  
# - If confidence = 0.7 (70% confident) → Use 70% my_estimate + 30% reference_value

# Let's work through this with simple numbers first:
my_estimate = 8.0        # I think this restaurant is 8/10
reference_value = 6.0    # But the city average is 6/10
confidence = 0.7         # I'm 70% confident in my estimate

print(f"My estimate: {my_estimate}")
print(f"Reference (city average): {reference_value}")
print(f"My confidence: {confidence}")
print()

# Apply the shrinkage formula:
final_value = (confidence * my_estimate) + ((1 - confidence) * reference_value)

print(f"Calculation: ({confidence} × {my_estimate}) + ({1-confidence} × {reference_value})")
print(f"           = {confidence * my_estimate} + {(1-confidence) * reference_value}")
print(f"           = {final_value}")
print()
print(f"So instead of {my_estimate}, I'd estimate {final_value}")
print()

print("Notice: The final value is between my estimate and the reference!")
print("This is called 'shrinking toward' the reference value.")
print()
print("=" * 60)
print()

# ═══ STEP 3: WHERE DOES CONFIDENCE COME FROM? ═══

print("=== Step 3: Calculating Confidence from Sample Size ===")
print()

print("Confidence isn't just picked randomly - it comes from your DATA!")
print("Specifically: HOW MANY data points you have.")
print()

# The confidence formula:
# confidence = sample_size / (sample_size + constant)
#
# Where:
# - sample_size = number of cases/reviews/data points you have
# - constant = how conservative you want to be (higher = more shrinkage)

def calculate_confidence(sample_size, conservative_factor=10):
    """
    Calculate confidence based on sample size.
    
    Args:
        sample_size: Number of data points (cases, reviews, etc.)
        conservative_factor: Higher = more conservative = more shrinkage
    
    Returns:
        float: Confidence between 0 and 1
    """
    return sample_size / (sample_size + conservative_factor)

# Let's see how confidence changes with different sample sizes:
print("Sample Size → Confidence (using conservative_factor=10)")
print("-" * 50)

sample_sizes = [1, 2, 5, 10, 20, 50, 100]
for size in sample_sizes:
    conf = calculate_confidence(size, conservative_factor=10)
    print(f"{size:3d} cases   → {conf:.3f} confidence")

print()
print("See the pattern? More cases = higher confidence = less shrinkage!")
print()

# Now let's apply this to jurisdiction data:
print("=" * 60)
print("=== Applied to Your Jurisdiction Problem ===")
print()

# Simulating your jurisdiction data:
jurisdictions = {
    "Queens County": {"cases": 3, "raw_average": 85000},      # Few cases, high average
    "Nassau County": {"cases": 15, "raw_average": 49000},     # Medium cases, medium average  
    "Suffolk County": {"cases": 45, "raw_average": 55000}     # Many cases, lower average
}

global_reference = 60000  # Let's say this is your overall average

print(f"Global reference average: ${global_reference:,}")
print()

for jurisdiction, data in jurisdictions.items():
    cases = data["cases"]
    raw_avg = data["raw_average"]
    
    # Calculate confidence from sample size
    confidence = calculate_confidence(cases, conservative_factor=10)
    
    # Apply shrinkage
    adjusted_avg = (confidence * raw_avg) + ((1 - confidence) * global_reference)
    
    print(f"{jurisdiction}:")
    print(f"  Cases: {cases}")
    print(f"  Raw average: ${raw_avg:,}")
    print(f"  Confidence: {confidence:.3f}")
    print(f"  Adjusted average: ${adjusted_avg:,.0f}")
    print()
