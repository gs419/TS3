<?php

namespace Tests\Feature;

use Tests\TestCase;

class ExampleTest extends TestCase
{
    public function test_the_dashboard_loads(): void
    {
        $this->withoutVite();

        $this->get('/')
            ->assertOk()
            ->assertSee('Fortify screens are the first rebuild step')
            ->assertSee('Authentication baseline');
    }
}
