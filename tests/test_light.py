import asyncio
from ha_client import HomeAssistantClient

# Light toggle script to test the ha client
entity_id = "light.light_switch1_light"

async def test_light_toggle():
    ha = HomeAssistantClient()
    
    print("Testing Home Assistant connection")
    if not await ha.test_connection():
        print("Cannot connect to Home Assistant. Please check your .env file.")
        return

    print(f"\nGetting current state of {entity_id}")
    state = await ha.get_state(entity_id)
    if state:
        current_state = state.get("state", "unknown")
        friendly_name = state.get("attributes", {}).get("friendly_name", entity_id)
        print(f"{friendly_name}: {current_state}")
    else:
        print(f"Could not get state for {entity_id}")
        return
    
    print(f"\nToggling {entity_id}")
    success = await ha.toggle_light(entity_id)
    
    if success:
        print("Toggle command sent successfully!")
        await asyncio.sleep(1)
        new_state = await ha.get_state(entity_id)
        if new_state:
            new_state_value = new_state.get("state", "unknown")
            print(f"New state: {new_state_value}")
        else:
            print("Could not verify new state")
    else:
        print("Failed to toggle light")


if __name__ == "__main__":
    print("Light Toggle Test")
    print("==============")
    
    asyncio.run(test_light_toggle())
