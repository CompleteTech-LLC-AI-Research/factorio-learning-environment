"""Execute the real Lua cleanup against a small Factorio API test double."""

from pathlib import Path

from lupa.lua52 import LuaRuntime


def test_peaceful_cleanup_removes_worms_and_preserves_other_forces():
    lua = LuaRuntime()
    lua.execute(
        """
        storage = {utils = {}}
        defines = {events = {on_tick = 1}}
        script = {on_event = function(...) end}
        entities = {
            {type = "unit", force = "enemy", valid = true},
            {type = "unit-spawner", force = "enemy", valid = true},
            {type = "turret", force = "enemy", valid = true},
            {type = "turret", force = "player", valid = true},
            {type = "simple-entity", force = "neutral", valid = true}
        }
        for _, entity in ipairs(entities) do
            entity.destroy = function() entity.valid = false end
        end
        game = {
            forces = {enemy = {kill_all_units = function()
                for _, entity in ipairs(entities) do
                    if entity.force == "enemy" and entity.type == "unit" then
                        entity.destroy()
                    end
                end
            end}},
            map_settings = {
                enemy_expansion = {enabled = true},
                enemy_evolution = {enabled = true}
            },
            surfaces = {{find_entities_filtered = function(filter)
                local found = {}
                for _, entity in ipairs(entities) do
                    if entity.valid
                        and (not filter.type or filter.type == entity.type)
                        and (not filter.force or filter.force == entity.force) then
                        table.insert(found, entity)
                    end
                end
                return found
            end}}
        }
        """
    )
    source = Path(__file__).resolve().parents[2] / "fle/env/mods/utils.lua"
    lua.execute(source.read_text())
    lua.globals().storage.utils.remove_enemies()
    assert [lua.globals().entities[i].valid for i in range(1, 6)] == [
        False,
        False,
        False,
        True,
        True,
    ]
    settings = lua.globals().game.map_settings
    assert not settings.enemy_expansion.enabled
    assert not settings.enemy_evolution.enabled
