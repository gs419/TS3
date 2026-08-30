<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Airport extends Model
{
    use HasFactory;

    protected $fillable = [
        'code',
        'name',
        'storage_path',
    ];

    public function databaseVariants(): HasMany
    {
        return $this->hasMany(DatabaseVariant::class);
    }

    public function instrumentSets(): HasMany
    {
        return $this->hasMany(InstrumentSet::class);
    }

    public function workspaces(): HasMany
    {
        return $this->hasMany(Workspace::class);
    }
}
