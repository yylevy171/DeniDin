# Bugfix 060: User request should ALWAYS win over system prompt

## Problem
The system often prioritizes restrictive system prompt instructions (like refusing to process because of constraints or missing data policies) even when the user explicitly commands it to proceed. The core principle must be: "User is GOD!" 

## Solution
Update the runtime constitution and AI handling logic to ensure that explicit user overrides always take precedence over system-level restrictions and prompts. If the operator explicitly commands an action, the system must execute it.
