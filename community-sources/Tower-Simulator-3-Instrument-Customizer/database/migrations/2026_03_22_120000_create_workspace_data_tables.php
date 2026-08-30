<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('airports', function (Blueprint $table) {
            $table->id();
            $table->string('code')->unique();
            $table->string('name')->nullable();
            $table->string('storage_path');
            $table->timestamps();
        });

        Schema::create('database_variants', function (Blueprint $table) {
            $table->id();
            $table->foreignId('airport_id')->constrained()->cascadeOnDelete();
            $table->string('name');
            $table->string('relative_path');
            $table->string('airport_file_relative_path')->nullable();
            $table->boolean('uses_default_airport_geometry')->default(false);
            $table->timestamps();

            $table->unique(['airport_id', 'name']);
        });

        Schema::create('instrument_sets', function (Blueprint $table) {
            $table->id();
            $table->foreignId('airport_id')->constrained()->cascadeOnDelete();
            $table->string('name');
            $table->string('relative_path');
            $table->boolean('has_adirs')->default(false);
            $table->boolean('has_dbright')->default(false);
            $table->boolean('has_weather')->default(false);
            $table->boolean('has_strips')->default(false);
            $table->timestamps();

            $table->unique(['airport_id', 'name']);
        });

        Schema::create('workspaces', function (Blueprint $table) {
            $table->id();
            $table->uuid('public_id')->unique();
            $table->foreignId('user_id')->nullable()->constrained()->nullOnDelete();
            $table->string('browser_session_id')->nullable()->index();
            $table->foreignId('airport_id')->constrained()->cascadeOnDelete();
            $table->foreignId('database_variant_id')->constrained()->cascadeOnDelete();
            $table->foreignId('instrument_set_id')->constrained()->cascadeOnDelete();
            $table->string('name')->nullable();
            $table->string('status')->default('draft');
            $table->timestamps();
        });

        Schema::create('workspace_screens', function (Blueprint $table) {
            $table->id();
            $table->foreignId('workspace_id')->constrained()->cascadeOnDelete();
            $table->string('screen_type');
            $table->string('base_file_name');
            $table->string('base_file_hash')->nullable();
            $table->json('changes_json')->nullable();
            $table->longText('export_text')->nullable();
            $table->timestamps();

            $table->unique(['workspace_id', 'screen_type']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('workspace_screens');
        Schema::dropIfExists('workspaces');
        Schema::dropIfExists('instrument_sets');
        Schema::dropIfExists('database_variants');
        Schema::dropIfExists('airports');
    }
};
