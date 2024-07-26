import {
  Controller,
  Get,
  Param,
  Query,
  Redirect,
  Logger,
} from '@nestjs/common';
import { SpotifyService } from './spotify.service';
import {
  ApiTags,
  ApiOperation,
  ApiParam,
  ApiQuery,
  ApiResponse,
} from '@nestjs/swagger';
import { Provider } from '../provider.entity';

@ApiTags('Provider: Spotify')
@Controller('providers/spotify')
export class SpotifyController {
  private readonly logger = new Logger(SpotifyController.name);

  constructor(private readonly spotifyService: SpotifyService) {}

  @Get('auth/authorize')
  @ApiOperation({ summary: 'Authorize Spotify account' })
  @Redirect()
  async authorize() {
    return {
      url: await this.spotifyService.getAuthorizationURL(),
      statusCode: 302,
    };
  }

  @Get('auth/callback')
  @ApiOperation({ summary: 'Spotify callback with authorization code' })
  @ApiQuery({ name: 'code', required: true, description: 'Authorization code' })
  @ApiResponse({
    status: 200,
    description: 'Spotify account authorized',
    type: Provider,
  })
  async callback(@Query('code') code: string) {
    try {
      return await this.spotifyService.upsertSpotifyAccount(code);
    } catch (error) {
      this.logger.error('Error during Spotify callback:', error);
      throw new Error('Failed to authorize Spotify account');
    }
  }

  @Get(':accountId/enable')
  @ApiOperation({ summary: 'Enable a Spotify account' })
  @ApiParam({ name: 'accountId', description: 'Spotify Account ID' })
  @ApiResponse({
    status: 200,
    description: 'Spotify account enabled',
    type: Provider,
  })
  async enable(@Param('accountId') accountId: string) {
    try {
      return await this.spotifyService.toggleSpotifyAccount(accountId, true);
    } catch (error) {
      this.logger.error(`Error enabling Spotify account ${accountId}:`, error);
      throw new Error(`Failed to enable Spotify account ${accountId}`);
    }
  }

  @Get(':accountId/disable')
  @ApiOperation({ summary: 'Disable a Spotify account' })
  @ApiParam({ name: 'accountId', description: 'Spotify Account ID' })
  @ApiResponse({
    status: 200,
    description: 'Spotify account disabled',
    type: Provider,
  })
  async disable(@Param('accountId') accountId: string) {
    try {
      return await this.spotifyService.toggleSpotifyAccount(accountId, false);
    } catch (error) {
      this.logger.error(`Error disabling Spotify account ${accountId}:`, error);
      throw new Error(`Failed to disable Spotify account ${accountId}`);
    }
  }

  @Get('accounts/active')
  @ApiOperation({ summary: 'Get all active Spotify accounts' })
  async getActiveAccounts() {
    try {
      return await this.spotifyService.getActiveSpotifyAccounts();
    } catch (error) {
      this.logger.error('Error fetching active Spotify accounts:', error);
      throw new Error('Failed to fetch active Spotify accounts');
    }
  }
}
