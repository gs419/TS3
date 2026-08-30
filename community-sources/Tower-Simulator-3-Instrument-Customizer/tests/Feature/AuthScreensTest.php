<?php

namespace Tests\Feature;

use App\Models\Airport;
use App\Models\DatabaseVariant;
use App\Models\InstrumentSet;
use App\Models\User;
use App\Models\Workspace;
use App\Models\WorkspaceScreen;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

class AuthScreensTest extends TestCase
{
    use RefreshDatabase;

    protected ?string $towerCatalogPath = null;

    public function test_guest_can_view_login_screen(): void
    {
        $this->withoutVite();

        $this->get(route('login'))
            ->assertOk()
            ->assertSee('Log in');
    }

    public function test_guest_can_view_registration_screen(): void
    {
        $this->withoutVite();

        $this->get(route('register'))
            ->assertOk()
            ->assertSee('Register');
    }

    public function test_guest_can_view_forgot_password_screen(): void
    {
        $this->withoutVite();

        $this->get(route('password.request'))
            ->assertOk()
            ->assertSee('Request a reset link');
    }

    public function test_guest_can_view_reset_password_screen(): void
    {
        $this->withoutVite();

        $this->get(route('password.reset', ['token' => 'test-token']))
            ->assertOk()
            ->assertSee('Set a new password');
    }

    public function test_authenticated_user_can_view_account_screen(): void
    {
        $this->withoutVite();

        $user = User::factory()->create();

        $this->actingAs($user)
            ->get(route('account'))
            ->assertOk()
            ->assertSee('Security and profile settings')
            ->assertSee('Two-factor authentication');
    }

    public function test_guest_is_redirected_from_account_screen(): void
    {
        $this->get(route('account'))
            ->assertRedirect(route('login'));
    }

    public function test_authenticated_user_can_view_workspace_overview(): void
    {
        $this->withoutVite();

        $user = User::factory()->create();
        $airport = Airport::create([
            'code' => 'KLAX',
            'name' => 'Los Angeles International',
            'storage_path' => 'KLAX',
        ]);
        $databaseVariant = DatabaseVariant::create([
            'airport_id' => $airport->id,
            'name' => 'default',
            'relative_path' => 'databases/default',
            'airport_file_relative_path' => 'databases/default/KLAX.airport',
            'uses_default_airport_geometry' => false,
        ]);
        $instrumentSet = InstrumentSet::create([
            'airport_id' => $airport->id,
            'name' => 'default-2.0',
            'relative_path' => 'instruments/default-2.0',
            'has_adirs' => true,
            'has_dbright' => true,
            'has_weather' => true,
            'has_strips' => true,
        ]);
        $workspace = Workspace::create([
            'public_id' => (string) str()->uuid(),
            'user_id' => $user->id,
            'airport_id' => $airport->id,
            'database_variant_id' => $databaseVariant->id,
            'instrument_set_id' => $instrumentSet->id,
            'name' => 'KLAX default workspace',
            'status' => 'draft',
        ]);
        WorkspaceScreen::create([
            'workspace_id' => $workspace->id,
            'screen_type' => 'adirs',
            'base_file_name' => 'adirslook.csv',
        ]);

        $this->actingAs($user)
            ->get(route('workspaces.index'))
            ->assertOk()
            ->assertSee('Your workspace overview')
            ->assertSee('KLAX default workspace')
            ->assertSee('default-2.0');
    }

    public function test_authenticated_user_can_view_create_workspace_screen(): void
    {
        $this->withoutVite();

        $user = User::factory()->create();
        $airport = Airport::create([
            'code' => 'KLAX',
            'name' => 'Los Angeles International',
            'storage_path' => 'KLAX',
        ]);
        DatabaseVariant::create([
            'airport_id' => $airport->id,
            'name' => 'default',
            'relative_path' => 'databases/default',
            'airport_file_relative_path' => 'databases/default/KLAX.airport',
            'uses_default_airport_geometry' => false,
        ]);
        InstrumentSet::create([
            'airport_id' => $airport->id,
            'name' => 'default-2.0',
            'relative_path' => 'instruments/default-2.0',
            'has_adirs' => true,
            'has_dbright' => true,
            'has_weather' => true,
            'has_strips' => true,
        ]);

        $this->actingAs($user)
            ->get(route('workspaces.create'))
            ->assertOk()
            ->assertSee('Create a workspace')
            ->assertSee('Base instrument set')
            ->assertSee('KLAX')
            ->assertSee('default')
            ->assertSee('default-2.0');
    }

    public function test_create_workspace_screen_imports_catalog_options_from_tower_data_when_database_is_empty(): void
    {
        $this->withoutVite();

        $user = User::factory()->create();
        $this->towerCatalogPath = storage_path('app/testing/workspace-form-tower-data');

        File::deleteDirectory($this->towerCatalogPath);
        File::ensureDirectoryExists($this->towerCatalogPath.'/KLAX/databases/default');
        File::ensureDirectoryExists($this->towerCatalogPath.'/KLAX/instruments/default-2.0');
        File::put($this->towerCatalogPath.'/KLAX/databases/default/KLAX.airport', '{}');
        File::put($this->towerCatalogPath.'/KLAX/instruments/default-2.0/adirslook.csv', 'test');
        File::put($this->towerCatalogPath.'/KLAX/instruments/default-2.0/dbrightlook.csv', 'test');
        File::put($this->towerCatalogPath.'/KLAX/instruments/default-2.0/striplook.csv', 'test');

        config()->set('tower.sample_airports_root', $this->towerCatalogPath);

        $this->actingAs($user)
            ->get(route('workspaces.create'))
            ->assertOk()
            ->assertSee('Create a workspace')
            ->assertSee('KLAX')
            ->assertSee('default')
            ->assertSee('default-2.0');

        $this->assertDatabaseHas('airports', [
            'code' => 'KLAX',
            'storage_path' => 'KLAX',
        ]);
        $this->assertDatabaseHas('database_variants', [
            'name' => 'default',
            'relative_path' => 'databases/default',
        ]);
        $this->assertDatabaseHas('instrument_sets', [
            'name' => 'default-2.0',
            'relative_path' => 'instruments/default-2.0',
            'has_adirs' => true,
            'has_dbright' => true,
            'has_weather' => false,
            'has_strips' => true,
        ]);
    }

    public function test_authenticated_user_can_create_a_workspace(): void
    {
        $user = User::factory()->create();
        $airport = Airport::create([
            'code' => 'KLAX',
            'name' => 'Los Angeles International',
            'storage_path' => 'KLAX',
        ]);
        $databaseVariant = DatabaseVariant::create([
            'airport_id' => $airport->id,
            'name' => 'default',
            'relative_path' => 'databases/default',
            'airport_file_relative_path' => 'databases/default/KLAX.airport',
            'uses_default_airport_geometry' => false,
        ]);
        $instrumentSet = InstrumentSet::create([
            'airport_id' => $airport->id,
            'name' => 'default-2.0',
            'relative_path' => 'instruments/default-2.0',
            'has_adirs' => true,
            'has_dbright' => true,
            'has_weather' => true,
            'has_strips' => true,
        ]);

        $response = $this->actingAs($user)
            ->post(route('workspaces.store'), [
                'name' => 'KLAX morning',
                'airport_id' => $airport->id,
                'database_variant_id' => $databaseVariant->id,
                'instrument_set_id' => $instrumentSet->id,
            ]);

        $workspace = Workspace::query()->first();

        $response
            ->assertRedirect(route('workspaces.show', $workspace))
            ->assertSessionHas('status');

        $this->assertNotNull($workspace);
        $this->assertSame('KLAX morning', $workspace->name);
        $this->assertSame($user->id, $workspace->user_id);
        $this->assertSame(4, $workspace->screens()->count());
        $this->assertSame(
            ['adirs', 'dbright', 'strips', 'weather'],
            $workspace->screens()->orderBy('screen_type')->pluck('screen_type')->all(),
        );
        $this->assertSame(
            [
                'adirs' => 'adirslook.csv',
                'dbright' => 'dbrightlook.csv',
                'strips' => 'striplook.csv',
                'weather' => 'weatherlook.csv',
            ],
            $workspace->screens()
                ->orderBy('screen_type')
                ->pluck('base_file_name', 'screen_type')
                ->all(),
        );
    }

    public function test_authenticated_user_can_view_workspace_detail_screen(): void
    {
        $this->withoutVite();

        $user = User::factory()->create();
        [$workspace] = $this->makeWorkspaceForUser($user);

        $this->actingAs($user)
            ->get(route('workspaces.show', $workspace))
            ->assertOk()
            ->assertSee($workspace->name)
            ->assertSee('Screen bases');
    }

    public function test_authenticated_user_can_view_edit_workspace_screen(): void
    {
        $this->withoutVite();

        $user = User::factory()->create();
        [$workspace] = $this->makeWorkspaceForUser($user);

        $this->actingAs($user)
            ->get(route('workspaces.edit', $workspace))
            ->assertOk()
            ->assertSee('Edit workspace')
            ->assertSee($workspace->name);
    }

    public function test_authenticated_user_can_update_a_workspace(): void
    {
        $user = User::factory()->create();
        [$workspace, $airport] = $this->makeWorkspaceForUser($user);
        $databaseVariant = DatabaseVariant::create([
            'airport_id' => $airport->id,
            'name' => 'night',
            'relative_path' => 'databases/night',
            'airport_file_relative_path' => null,
            'uses_default_airport_geometry' => true,
        ]);
        $instrumentSet = InstrumentSet::create([
            'airport_id' => $airport->id,
            'name' => 'radar-only',
            'relative_path' => 'instruments/radar-only',
            'has_adirs' => false,
            'has_dbright' => true,
            'has_weather' => false,
            'has_strips' => false,
        ]);

        $this->actingAs($user)
            ->put(route('workspaces.update', $workspace), [
                'name' => 'KLAX evening',
                'airport_id' => $airport->id,
                'database_variant_id' => $databaseVariant->id,
                'instrument_set_id' => $instrumentSet->id,
            ])
            ->assertRedirect(route('workspaces.show', $workspace))
            ->assertSessionHas('status');

        $workspace->refresh();

        $this->assertSame('KLAX evening', $workspace->name);
        $this->assertSame($databaseVariant->id, $workspace->database_variant_id);
        $this->assertSame($instrumentSet->id, $workspace->instrument_set_id);
    }

    public function test_authenticated_user_can_delete_a_workspace(): void
    {
        $user = User::factory()->create();
        [$workspace] = $this->makeWorkspaceForUser($user);

        $this->actingAs($user)
            ->delete(route('workspaces.destroy', $workspace))
            ->assertRedirect(route('workspaces.index'))
            ->assertSessionHas('status');

        $this->assertDatabaseMissing('workspaces', [
            'id' => $workspace->id,
        ]);
        $this->assertDatabaseMissing('workspace_screens', [
            'workspace_id' => $workspace->id,
        ]);
    }

    public function test_authenticated_user_can_view_adirs_sidebar_editor(): void
    {
        $this->withoutVite();

        $user = User::factory()->create();
        [$workspace] = $this->makeWorkspaceForUser($user);
        $this->seedTowerDataForWorkspace($workspace);

        $this->actingAs($user)
            ->get(route('workspaces.screens.adirs.edit', $workspace))
            ->assertOk()
            ->assertSee('Live preview')
            ->assertSee('Save ADIRS changes');
    }

    public function test_authenticated_user_can_save_adirs_sidebar_changes(): void
    {
        $user = User::factory()->create();
        [$workspace] = $this->makeWorkspaceForUser($user);
        $this->seedTowerDataForWorkspace($workspace);

        $this->actingAs($user)
            ->put(route('workspaces.screens.adirs.update', $workspace), [
                'changes_json' => json_encode([
                    'styles' => [
                        'Background color' => '1,2,3,255',
                    ],
                    'areas' => [
                        [
                            'color_raw' => '4,5,6,255',
                        ],
                    ],
                    'meta' => [
                        'show_labels' => false,
                    ],
                ], JSON_THROW_ON_ERROR),
            ])
            ->assertRedirect(route('workspaces.screens.adirs.edit', $workspace))
            ->assertSessionHas('status');

        $screen = $workspace->screens()->where('screen_type', 'adirs')->firstOrFail()->fresh();

        $this->assertSame([
            'styles' => [
                'Background color' => '1,2,3,255',
            ],
            'areas' => [
                [
                    'color_raw' => '4,5,6,255',
                ],
            ],
            'meta' => [
                'show_labels' => false,
            ],
        ], $screen->changes_json);
    }

    public function test_guest_is_redirected_from_workspace_overview(): void
    {
        $this->get(route('workspaces.index'))
            ->assertRedirect(route('login'));
    }

    public function test_guest_is_redirected_from_create_workspace_screen(): void
    {
        $this->get(route('workspaces.create'))
            ->assertRedirect(route('login'));
    }

    public function test_guest_is_redirected_from_workspace_detail_screen(): void
    {
        $user = User::factory()->create();
        [$workspace] = $this->makeWorkspaceForUser($user);

        $this->get(route('workspaces.show', $workspace))
            ->assertRedirect(route('login'));
    }

    public function test_guest_is_redirected_from_edit_workspace_screen(): void
    {
        $user = User::factory()->create();
        [$workspace] = $this->makeWorkspaceForUser($user);

        $this->get(route('workspaces.edit', $workspace))
            ->assertRedirect(route('login'));
    }

    public function test_user_cannot_access_another_users_workspace_routes(): void
    {
        $this->withoutVite();

        $owner = User::factory()->create();
        $otherUser = User::factory()->create();
        [$workspace, $airport, $databaseVariant, $instrumentSet] = $this->makeWorkspaceForUser($owner);
        $this->seedTowerDataForWorkspace($workspace);

        $this->actingAs($otherUser)
            ->get(route('workspaces.show', $workspace))
            ->assertNotFound();

        $this->actingAs($otherUser)
            ->get(route('workspaces.edit', $workspace))
            ->assertNotFound();

        $this->actingAs($otherUser)
            ->put(route('workspaces.update', $workspace), [
                'name' => 'Hijack',
                'airport_id' => $airport->id,
                'database_variant_id' => $databaseVariant->id,
                'instrument_set_id' => $instrumentSet->id,
            ])
            ->assertNotFound();

        $this->actingAs($otherUser)
            ->delete(route('workspaces.destroy', $workspace))
            ->assertNotFound();

        $this->actingAs($otherUser)
            ->get(route('workspaces.screens.adirs.edit', $workspace))
            ->assertNotFound();

        $this->actingAs($otherUser)
            ->put(route('workspaces.screens.adirs.update', $workspace), [
                'changes_json' => json_encode(['styles' => []], JSON_THROW_ON_ERROR),
            ])
            ->assertNotFound();
    }

    public function test_unverified_user_can_view_verify_email_screen(): void
    {
        $this->withoutVite();

        $user = User::factory()->unverified()->create();

        $this->actingAs($user)
            ->get(route('verification.notice'))
            ->assertOk()
            ->assertSee('Check your inbox');
    }

    public function test_authenticated_user_can_view_confirm_password_screen(): void
    {
        $this->withoutVite();

        $user = User::factory()->create();

        $this->actingAs($user)
            ->get(route('password.confirm'))
            ->assertOk()
            ->assertSee('Re-enter your password');
    }

    public function test_two_factor_challenge_redirects_to_login_without_challenged_session(): void
    {
        $this->get(route('two-factor.login'))
            ->assertRedirect(route('login'));
    }

    protected function tearDown(): void
    {
        if ($this->towerCatalogPath) {
            File::deleteDirectory($this->towerCatalogPath);
        }

        parent::tearDown();
    }

    protected function makeWorkspaceForUser(User $user): array
    {
        $airport = Airport::create([
            'code' => 'KLAX',
            'name' => 'Los Angeles International',
            'storage_path' => 'KLAX',
        ]);
        $databaseVariant = DatabaseVariant::create([
            'airport_id' => $airport->id,
            'name' => 'default',
            'relative_path' => 'databases/default',
            'airport_file_relative_path' => 'databases/default/KLAX.airport',
            'uses_default_airport_geometry' => false,
        ]);
        $instrumentSet = InstrumentSet::create([
            'airport_id' => $airport->id,
            'name' => 'default-2.0',
            'relative_path' => 'instruments/default-2.0',
            'has_adirs' => true,
            'has_dbright' => true,
            'has_weather' => true,
            'has_strips' => true,
        ]);
        $workspace = Workspace::create([
            'public_id' => (string) str()->uuid(),
            'user_id' => $user->id,
            'airport_id' => $airport->id,
            'database_variant_id' => $databaseVariant->id,
            'instrument_set_id' => $instrumentSet->id,
            'name' => 'KLAX default workspace',
            'status' => 'draft',
        ]);
        WorkspaceScreen::create([
            'workspace_id' => $workspace->id,
            'screen_type' => 'adirs',
            'base_file_name' => 'adirslook.csv',
        ]);

        return [$workspace, $airport, $databaseVariant, $instrumentSet];
    }

    protected function seedTowerDataForWorkspace(Workspace $workspace): void
    {
        $root = storage_path('app/tower_data/'.$workspace->airport->storage_path);

        File::deleteDirectory($root);
        File::ensureDirectoryExists($root.'/databases/default');
        File::ensureDirectoryExists($root.'/instruments/default-2.0');

        File::put($root.'/databases/default/'.$workspace->airport->code.'.airport', json_encode([
            '_centerlat' => 33.942501068115237,
            '_centerlon' => -118.40799713134766,
            'icao' => $workspace->airport->code,
            'name' => 'Los Angeles International Airport',
            'roads' => [
                [
                    'name' => 'AA',
                    'type' => 0,
                    'width' => 40,
                    'knots' => [
                        ['pos' => ['x' => 0, 'z' => 0], 'name' => '', 'sayname' => ''],
                        ['pos' => ['x' => 100, 'z' => 100], 'name' => 'H1', 'sayname' => 'Hotel One'],
                    ],
                ],
            ],
        ], JSON_THROW_ON_ERROR));

        File::put($root.'/instruments/default-2.0/adirslook.csv', <<<CSV
Background color,"0,96,119,255"
Taxiway color,"45,45,45,255"
Taxiway thickness,25
Runway color,"15,15,15,255"
Runway thickness,45
Terminal color,"0,0,0,255"
Terminal thickness,0
Road area color,"0,0,0,255"
Road area thickness,0
Road text background color,"128,128,128,255"
Road text color,"255,255,255,255"
Point text background color,"120,120,200,255"
Point text color,"1,1,1,255"
Area,"33.9425010681,-118.4079971313
33.9426010681,-118.4079971313
33.9426010681,-118.4078971313
Color=73,73,73,255"
CSV);
    }
}
