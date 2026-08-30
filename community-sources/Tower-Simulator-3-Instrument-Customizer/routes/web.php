<?php

use App\Http\Controllers\AccountController;
use App\Http\Controllers\WorkspaceAdirsController;
use App\Http\Controllers\WorkspaceController;
use Illuminate\Support\Facades\Route;

Route::view('/', 'dashboard')->name('dashboard');
Route::get('/account', AccountController::class)
    ->middleware('auth')
    ->name('account');
Route::get('/workspaces', [WorkspaceController::class, 'index'])
    ->middleware('auth')
    ->name('workspaces.index');
Route::get('/workspaces/create', [WorkspaceController::class, 'create'])
    ->middleware('auth')
    ->name('workspaces.create');
Route::post('/workspaces', [WorkspaceController::class, 'store'])
    ->middleware('auth')
    ->name('workspaces.store');
Route::get('/workspaces/{workspace}', [WorkspaceController::class, 'show'])
    ->middleware('auth')
    ->name('workspaces.show');
Route::get('/workspaces/{workspace}/edit', [WorkspaceController::class, 'edit'])
    ->middleware('auth')
    ->name('workspaces.edit');
Route::put('/workspaces/{workspace}', [WorkspaceController::class, 'update'])
    ->middleware('auth')
    ->name('workspaces.update');
Route::delete('/workspaces/{workspace}', [WorkspaceController::class, 'destroy'])
    ->middleware('auth')
    ->name('workspaces.destroy');
Route::get('/workspaces/{workspace}/screens/adirs', [WorkspaceAdirsController::class, 'edit'])
    ->middleware('auth')
    ->name('workspaces.screens.adirs.edit');
Route::put('/workspaces/{workspace}/screens/adirs', [WorkspaceAdirsController::class, 'update'])
    ->middleware('auth')
    ->name('workspaces.screens.adirs.update');
